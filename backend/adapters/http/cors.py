"""Parse the explicit browser-origin allowlist at application composition."""

import os
import re
from ipaddress import ip_address
from urllib.parse import urlsplit

from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send


class ScopedCORSMiddleware:
    """Keep browser writes limited to the existing quotation submission route."""

    def __init__(self, app: ASGIApp, allow_origins: list[str]) -> None:
        self.reads = CORSMiddleware(
            app,
            allow_origins=allow_origins,
            allow_methods=["GET"],
            allow_credentials=False,
        )
        self.quotations = CORSMiddleware(
            app,
            allow_origins=allow_origins,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
            allow_credentials=False,
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        middleware = (
            self.quotations
            if scope["type"] == "http" and scope["path"] == "/quotations"
            else self.reads
        )
        await middleware(scope, receive, send)


def get_cors_allowed_origins() -> list[str]:
    value = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    if not value:
        return []

    origins: list[str] = []
    for entry in value.split(","):
        origin = entry.strip()
        try:
            parsed = urlsplit(origin)
            host = parsed.hostname
            if (
                parsed.scheme not in ("http", "https")
                or not host
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or "?" in origin
                or "#" in origin
                or "*" in origin
                or any(character.isspace() for character in origin)
                or parsed.netloc.endswith(":")
                or not re.fullmatch(
                    r"(?:[a-zA-Z0-9.-]+|\[[0-9a-fA-F:.]+\])(?::[0-9]+)?",
                    parsed.netloc,
                )
            ):
                raise ValueError
            # Accessing port also validates its numeric form and range.
            _ = parsed.port
            if ":" in host or re.fullmatch(r"[0-9.]+", host):
                ip_address(host)
            elif len(host) > 253 or not re.fullmatch(
                r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
                r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*",
                host,
            ):
                raise ValueError
        except ValueError as error:
            raise ValueError(
                "CORS_ALLOWED_ORIGINS requires comma-separated exact HTTP(S) "
                f"origins without credentials, paths or wildcards: {origin!r}"
            ) from error
        if origin not in origins:
            origins.append(origin)
    return origins

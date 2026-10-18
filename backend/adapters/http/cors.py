"""Parse the explicit browser-origin allowlist at application composition."""

import os
import re
from collections.abc import Callable
from ipaddress import ip_address
from urllib.parse import urlsplit

from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send


def get_cors_allowed_origins() -> list[str]:
    return parse_cors_allowed_origins(os.getenv("CORS_ALLOWED_ORIGINS", ""))


def parse_cors_allowed_origins(value: str) -> list[str]:
    value = value.strip()
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


class EventCorsMiddleware:
    """Resolve each event's policy without sharing mutable middleware state."""

    def __init__(self, app: ASGIApp, origins: Callable[[], list[str]]) -> None:
        self.app = app
        self.origins = origins

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        policy = CORSMiddleware(
            self.app,
            allow_origins=self.origins(),
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
            allow_credentials=False,
        )
        await policy(scope, receive, send)

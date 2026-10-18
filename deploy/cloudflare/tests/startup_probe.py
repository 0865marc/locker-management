"""Bounded native readiness and process cleanup; no runtime installation here."""

import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Generator
from contextlib import contextmanager
from http.client import HTTPResponse, RemoteDisconnected
from pathlib import Path

CLIENT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def log_tail(path: Path) -> str:
    try:
        with path.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            stream.seek(max(0, stream.tell() - 65536))
            data = stream.read(65536)
        return b"\n".join(data.splitlines()[-120:]).decode("utf-8", errors="ignore")
    except OSError as error:
        return f"<log unavailable: {type(error).__name__}>"


@contextmanager
def worker_process(
    command: list[str], cwd: Path, logfile: Path
) -> Generator[subprocess.Popen[bytes]]:
    with logfile.open("wb") as output:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            yield process
        except Exception as error:
            status = process.poll()
            print(
                f"Startup/contract failure: {type(error).__name__}: {error}; "
                f"process status before cleanup: {status if status is not None else 'running'}\n"
                f"Last runtime log (at most 120 lines / 64 KiB):\n{log_tail(logfile)}",
                flush=True,
            )
            raise
        finally:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=10)


def wait_until_ready(
    process: subprocess.Popen[bytes],
    url: str,
    decode: Callable[[HTTPResponse], object] | None = None,
) -> object:
    deadline = time.monotonic() + 90
    last_error: Exception | None = None
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(
                f"Worker readiness timed out after 90 seconds; "
                f"last connection error: {last_error!r}"
            ) from last_error
        status = process.poll()
        if status is not None:
            raise RuntimeError(
                f"Worker exited before readiness (status={status}); "
                f"last connection error: {last_error!r}"
            )
        try:
            with CLIENT.open(url, timeout=min(1.0, remaining)) as response:
                if decode is not None:
                    result = decode(response)
                else:
                    result = None
        except (urllib.error.URLError, TimeoutError, RemoteDisconnected) as error:
            last_error = error
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Worker readiness timed out after 90 seconds; "
                    f"last connection error: {error!r}"
                ) from error
            time.sleep(0.05)
            continue
        if time.monotonic() >= deadline:
            raise TimeoutError("Worker response arrived after the 90 second deadline")
        return result

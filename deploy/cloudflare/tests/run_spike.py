"""Build and run the native experiment with isolated disposable local state."""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from startup_probe import wait_until_ready, worker_process

CLOUDFLARE = Path(__file__).resolve().parents[1]
ROOT = CLOUDFLARE.parents[1]
EVIDENCE = CLOUDFLARE / "evidence"
WRANGLER = [
    "node",
    "node_modules/wrangler/bin/wrangler.js",
    "--config",
    "wrangler.spike.jsonc",
]


def run(
    command: list[str], logfile: str, environment: dict[str, str] | None = None
) -> None:
    print("COMMAND " + json.dumps(command), flush=True)
    with (EVIDENCE / logfile).open("w") as output:
        result = subprocess.run(
            command,
            cwd=CLOUDFLARE,
            stdout=output,
            stderr=subprocess.STDOUT,
            check=False,
            env=environment,
        )
    if result.returncode:
        print((EVIDENCE / logfile).read_text(), flush=True)
        raise subprocess.CalledProcessError(result.returncode, command)


def available_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def main() -> None:
    EVIDENCE.mkdir(exist_ok=True)
    os.environ.setdefault("WRANGLER_SEND_METRICS", "false")
    os.environ.setdefault("UV_CACHE_DIR", str(ROOT / ".cache" / "uv"))
    os.environ.setdefault("npm_config_cache", str(ROOT / ".cache" / "npm"))
    os.environ.setdefault("XDG_CONFIG_HOME", str(CLOUDFLARE / ".wrangler" / "config"))
    os.environ.setdefault("XDG_CACHE_HOME", str(CLOUDFLARE / ".wrangler" / "cache"))
    run(
        [sys.executable, str(ROOT / "scripts/cloudflare/prepare_spike.py")],
        "prepare.log",
    )
    run(["uv", "sync", "--locked"], "install.log")
    context_environment = dict(os.environ)
    context_environment["PYTHONPATH"] = str(CLOUDFLARE / "runtime_spike")
    run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_event_context.py",
            "-v",
        ],
        "context-unit.log",
        context_environment,
    )
    run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_probe_units.py",
            "-v",
        ],
        "probe-units.txt",
        context_environment,
    )
    run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_startup_*.py",
            "-v",
        ],
        "startup-units.txt",
        context_environment,
    )
    run(["npm", "ci", "--ignore-scripts"], "npm-install.log")
    run(["uv", "run", "--locked", "pywrangler", "sync"], "sync.log")
    run(WRANGLER + ["deploy", "--dry-run", "--outdir", ".wrangler/build"], "build.log")
    state_root = CLOUDFLARE / ".wrangler"
    state_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="spike-", dir=state_root) as state:
        run(
            WRANGLER
            + [
                "d1",
                "execute",
                "runtime-spike",
                "--local",
                "--persist-to",
                state,
                "--file",
                "tests/schema.sql",
            ],
            "schema.log",
        )
        port = available_port()
        started = time.perf_counter()
        command = [
            "uv",
            "run",
            "--locked",
            "pywrangler",
            "dev",
            "--config",
            "wrangler.spike.jsonc",
            "--local",
            "--ip",
            "127.0.0.1",
            "--port",
            str(port),
            "--persist-to",
            state,
            "--show-interactive-dev-session=false",
        ]
        print("COMMAND " + json.dumps(command), flush=True)
        with worker_process(command, CLOUDFLARE, EVIDENCE / "runtime.log") as process:
            base_url = f"http://127.0.0.1:{port}"
            health = wait_until_ready(process, base_url + "/", decode=json.load)
            (EVIDENCE / "startup.json").write_text(
                json.dumps(
                    {
                        "local_process_to_first_response_wall_ms": (
                            time.perf_counter() - started
                        )
                        * 1000,
                        "health": health,
                    },
                    indent=2,
                )
                + "\n"
            )
            os.environ["SPIKE_BASE_URL"] = base_url
            run(
                [
                    sys.executable,
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "tests",
                    "-p",
                    "test_native_spike.py",
                    "-v",
                ],
                "native-tests.log",
            )
    print("Native feasibility checks passed; remote Free acceptance remains pending.")


if __name__ == "__main__":
    main()

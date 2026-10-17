"""Build and run the native experiment with isolated disposable local state."""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

CLOUDFLARE = Path(__file__).resolve().parents[1]
ROOT = CLOUDFLARE.parent
EVIDENCE = CLOUDFLARE / "evidence"
WRANGLER = ["node", "node_modules/wrangler/bin/wrangler.js"]
CLIENT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


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
        with (EVIDENCE / "runtime.log").open("w") as output:
            process = subprocess.Popen(
                command,
                cwd=CLOUDFLARE,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                base_url = f"http://127.0.0.1:{port}"
                deadline = time.monotonic() + 90
                while True:
                    if process.poll() is not None:
                        raise RuntimeError(
                            "Native runtime exited; inspect evidence/runtime.log"
                        )
                    try:
                        with CLIENT.open(base_url + "/", timeout=1) as response:
                            health: object = json.load(response)
                        break
                    except (urllib.error.URLError, TimeoutError):
                        if time.monotonic() >= deadline:
                            raise TimeoutError(
                                "Native runtime did not become ready in 90 seconds"
                            )
                        time.sleep(0.05)
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
            finally:
                # Terminate the launcher and its Wrangler/workerd descendants.
                import signal

                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=10)
    print("Native feasibility checks passed; remote Free acceptance remains pending.")


if __name__ == "__main__":
    main()

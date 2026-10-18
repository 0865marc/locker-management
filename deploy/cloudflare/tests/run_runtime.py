"""Build and exercise the production Python Worker with official local bindings.

Missing Python/WASM packages are a failing prerequisite, never a skipped test.
No account, credentials, resource creation or remote deployment is used.
"""

import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

from startup_probe import wait_until_ready, worker_process

ROOT = Path(__file__).resolve().parents[3]
CLOUDFLARE = ROOT / "deploy" / "cloudflare"
CONFIG = "wrangler.production.jsonc"
WRANGLER = ["node", "node_modules/wrangler/bin/wrangler.js"]


def run(command: list[str]) -> None:
    print("COMMAND " + " ".join(command), flush=True)
    subprocess.run(command, cwd=CLOUDFLARE, check=True)


def main() -> None:
    os.environ.setdefault("WRANGLER_SEND_METRICS", "false")
    os.environ.setdefault("UV_CACHE_DIR", str(ROOT / ".cache" / "uv"))
    os.environ.setdefault("XDG_CONFIG_HOME", str(CLOUDFLARE / ".wrangler" / "config"))
    os.environ.setdefault("XDG_CACHE_HOME", str(CLOUDFLARE / ".wrangler" / "cache"))
    run([sys.executable, str(ROOT / "scripts/cloudflare/prepare.py"), "--check"])
    run(["uv", "sync", "--locked"])
    run(["uv", "run", "--locked", "pywrangler", "sync"])
    run(
        WRANGLER
        + [
            "deploy",
            "--config",
            CONFIG,
            "--dry-run",
            "--outdir",
            ".wrangler/production-build",
        ]
    )
    with tempfile.TemporaryDirectory(prefix="locker-production-") as state:
        run(
            WRANGLER
            + [
                "d1",
                "migrations",
                "apply",
                "locker-management-demo",
                "--config",
                CONFIG,
                "--local",
                "--persist-to",
                state,
            ]
        )
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = int(listener.getsockname()[1])
        command = [
            "uv",
            "run",
            "--locked",
            "pywrangler",
            "dev",
            "--config",
            CONFIG,
            "--local",
            "--ip",
            "127.0.0.1",
            "--port",
            str(port),
            "--persist-to",
            state,
            "--show-interactive-dev-session=false",
        ]
        with worker_process(
            command, CLOUDFLARE, Path(state) / "runtime.log"
        ) as process:
            base_url = f"http://127.0.0.1:{port}"
            wait_until_ready(process, base_url + "/openapi.json")
            environment = dict(os.environ)
            environment["CLOUDFLARE_RUNTIME_BASE_URL"] = base_url
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "tests",
                    "-p",
                    "test_cloudflare_runtime.py",
                    "-v",
                ],
                cwd=CLOUDFLARE,
                env=environment,
                check=True,
            )
    print(
        "Production native Python/Queues local contracts passed; Free metrics remain pending."
    )


if __name__ == "__main__":
    main()

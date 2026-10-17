"""Prepare/check a fresh production Workers tree from explicit shared sources."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESTINATION = ROOT / "cloudflare" / ".production"
DIRECTORIES = (
    "domain",
    "application",
    "adapters/http",
    "adapters/runtime",
    "adapters/database/d1",
)
FILES = (
    "composition.py",
    "cloudflare_worker.py",
    "adapters/__init__.py",
    "adapters/database/__init__.py",
    "adapters/queue/__init__.py",
    "adapters/queue/cloudflare.py",
    "adapters/providers/__init__.py",
    "adapters/providers/simulated_shipping.py",
)


def sources() -> dict[str, bytes]:
    backend = ROOT / "backend"
    paths = [backend / path for path in FILES]
    for directory in DIRECTORIES:
        paths.extend(sorted((backend / directory).rglob("*.py")))
    result = {str(path.relative_to(backend)): path.read_bytes() for path in paths}
    manifest = {
        name: hashlib.sha256(content).hexdigest()
        for name, content in sorted(result.items())
    }
    result["manifest.json"] = (
        json.dumps(manifest, sort_keys=True, indent=2) + "\n"
    ).encode()
    return result


def prepare(*, check: bool = False) -> None:
    expected = sources()
    if check:
        actual = {
            str(path.relative_to(DESTINATION)): path.read_bytes()
            for path in DESTINATION.rglob("*")
            if path.is_file()
        }
        if actual != expected:
            raise SystemExit(
                "Workers staging is stale; run scripts/cloudflare/prepare.py"
            )
        print(f"Fresh production staging verified: {len(expected) - 1} sources")
        return
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    for name, content in expected.items():
        target = DESTINATION / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    print(f"Prepared {len(expected) - 1} production sources in {DESTINATION}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Fail on stale staging without editing it"
    )
    prepare(check=parser.parse_args().check)

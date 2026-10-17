"""Stage only the sources required by the initial native runtime experiment."""

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESTINATION = ROOT / "cloudflare" / ".prepared"
DIRECTORIES = (
    "backend/domain",
    "backend/application",
    "backend/adapters/http",
)
FILES = (
    "backend/adapters/__init__.py",
    "cloudflare/runtime_spike/worker.py",
    "cloudflare/runtime_spike/bindings.py",
    "cloudflare/runtime_spike/d1_probe.py",
    "cloudflare/runtime_spike/queue_probe.py",
    "cloudflare/runtime_spike/event_context.py",
    "cloudflare/runtime_spike/bootstrap.py",
    "cloudflare/runtime_spike/import_clock.py",
)


def main() -> None:
    paths = [ROOT / item for item in FILES]
    for directory in DIRECTORIES:
        paths.extend(sorted((ROOT / directory).rglob("*.py")))
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    manifest: dict[str, str] = {}
    for source in paths:
        if source.is_relative_to(ROOT / "backend"):
            relative = source.relative_to(ROOT / "backend")
        else:
            relative = Path(source.name)
        destination = DESTINATION / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        content = source.read_bytes()
        destination.write_bytes(content)
        manifest[str(source.relative_to(ROOT))] = hashlib.sha256(content).hexdigest()
    (DESTINATION / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    print(f"Prepared {len(paths)} Python sources in {DESTINATION}")


if __name__ == "__main__":
    main()

"""Read-only D1 migration compatibility check from the target release checkout."""

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[2]
HISTORY_SQL = "SELECT name FROM d1_migrations ORDER BY id"


def validate_history(expected: tuple[str, ...], applied: tuple[str, ...]) -> None:
    if not expected:
        raise ValueError("Target release has no declared compatible D1 migrations")
    if applied != expected:
        raise ValueError("D1 migration history is incompatible with the target release")


def history_from_response(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError("Invalid D1 migration history response")
    records = cast(list[object], value)
    if len(records) != 1:
        raise ValueError("Invalid D1 migration history response")
    record = records[0]
    if not isinstance(record, dict):
        raise ValueError("Invalid D1 migration history response")
    result = cast(dict[str, object], record)
    rows = result.get("results")
    if result.get("success") is not True or not isinstance(rows, list):
        raise ValueError("D1 migration history could not be read")
    names: list[str] = []
    for row in cast(list[object], rows):
        if not isinstance(row, dict):
            raise ValueError("Invalid D1 migration history row")
        name = cast(dict[str, object], row).get("name")
        if not isinstance(name, str):
            raise ValueError("Invalid D1 migration history name")
        names.append(name)
    return tuple(names)


def inspect_history(
    database: str, config: Path, *, remote: bool = False, persist_to: Path | None = None
) -> tuple[str, ...]:
    if remote and persist_to is not None:
        raise ValueError("Local persistence cannot be combined with --remote")
    command = [
        "node",
        str(ROOT / "cloudflare/node_modules/wrangler/bin/wrangler.js"),
        "d1",
        "execute",
        database,
        "--config",
        str(config),
        "--remote" if remote else "--local",
        "--json",
        "--command",
        HISTORY_SQL,
    ]
    if persist_to is not None:
        command += ["--persist-to", str(persist_to)]
    environment = dict(os.environ)
    environment["WRANGLER_SEND_METRICS"] = "false"
    result = subprocess.run(
        command,
        cwd=ROOT / "cloudflare",
        env=environment,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    if result.returncode:
        raise ValueError("Cannot inspect D1 migration history; no changes were made")
    decoded: object = json.loads(result.stdout)
    return history_from_response(decoded)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default="locker-management-demo")
    parser.add_argument(
        "--config", type=Path, default=ROOT / "cloudflare/wrangler.production.jsonc"
    )
    parser.add_argument(
        "--migrations", type=Path, default=ROOT / "cloudflare/migrations"
    )
    parser.add_argument("--persist-to", type=Path)
    parser.add_argument(
        "--remote", action="store_true", help="Read the explicitly configured remote D1"
    )
    args = parser.parse_args()
    expected = tuple(path.name for path in sorted(args.migrations.glob("*.sql")))
    try:
        applied = inspect_history(
            args.database,
            args.config.resolve(),
            remote=args.remote,
            persist_to=args.persist_to,
        )
        validate_history(expected, applied)
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"Schema compatibility check failed: {error}\n")
    print("D1 migration history matches the target release; no database changes made")


if __name__ == "__main__":
    main()

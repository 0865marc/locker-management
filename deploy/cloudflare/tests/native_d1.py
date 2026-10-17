"""CPython adapters against real local Miniflare D1; not Python/WASM evidence.

Run with backend + this directory on PYTHONPATH. Each context owns its process,
loopback port and ephemeral state. The transport never retries any operation.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import signal
import tempfile
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from adapters.database.d1.bindings import (
    D1BindingError,
    D1PreparedStatement,
    D1Value,
)


@dataclass(frozen=True)
class NativeStatement:
    database: NativeD1
    sql: str
    params: tuple[D1Value, ...] = ()

    def bind(self, *values: D1Value) -> NativeStatement:
        return NativeStatement(self.database, self.sql, values)

    def payload(self) -> dict[str, object]:
        return {"sql": self.sql, "params": list(self.params)}

    async def first(self) -> object:
        return await self.database.request({"op": "first", "statement": self.payload()})

    async def all(self) -> object:
        return await self.database.request({"op": "all", "statement": self.payload()})

    async def run(self) -> object:
        return await self.database.request({"op": "run", "statement": self.payload()})


class NativeD1:
    """An isolated test-only implementation of the raw D1 binding protocol."""

    def __init__(self, state_directory: Path | None = None) -> None:
        self._external_state = state_directory
        self.process: asyncio.subprocess.Process | None = None
        self.url = ""
        self._state: tempfile.TemporaryDirectory[str] | None = None
        self.statements: list[tuple[str, tuple[D1Value, ...]]] = []
        self.results: list[object] = []

    async def __aenter__(self) -> NativeD1:
        if self.process is not None:
            raise D1BindingError("D1 bridge is already running")
        script = Path(__file__).with_name("d1_bridge.mjs")
        if self._external_state is None:
            self._state = tempfile.TemporaryDirectory(prefix="locker-native-d1-")
            state_path = self._state.name
        else:
            if not self._external_state.is_dir():
                raise D1BindingError("External test state directory must already exist")
            state_path = str(self._external_state.resolve())
        try:
            self.process = await asyncio.create_subprocess_exec(
                "node",
                str(script),
                state_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
            assert self.process.stdout is not None
            line = await asyncio.wait_for(self.process.stdout.readline(), timeout=30)
            if not line:
                assert self.process.stderr is not None
                diagnostic = (await self.process.stderr.read()).decode()
                raise D1BindingError(f"Miniflare bridge failed to start: {diagnostic}")
            value: object = json.loads(line)
            if not isinstance(value, dict):
                raise D1BindingError("Invalid Miniflare bridge startup response")
            url = cast(dict[str, object], value).get("url")
            if not isinstance(url, str) or not url.startswith("http://127.0.0.1:"):
                raise D1BindingError("Bridge did not bind loopback")
            self.url = url
            return self
        except BaseException:
            await self.close()
            raise

    async def __aexit__(self, *_args: object) -> None:
        await self.close()

    async def close(self) -> None:
        process = self.process
        try:
            if process is not None:
                if process.stdin is not None:
                    process.stdin.close()
                try:
                    await asyncio.wait_for(process.communicate(), timeout=10)
                except TimeoutError:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    await process.communicate()
        finally:
            self.process = None
            self.url = ""
            if self._state is not None:
                self._state.cleanup()
                self._state = None

    def prepare(self, sql: str) -> NativeStatement:
        return NativeStatement(self, sql)

    async def batch(self, statements: Sequence[D1PreparedStatement]) -> object:
        payload: list[dict[str, object]] = []
        for statement in statements:
            if (
                not isinstance(statement, NativeStatement)
                or statement.database is not self
            ):
                raise D1BindingError("A batch must contain this bridge's statements")
            self.statements.append((statement.sql, statement.params))
            payload.append(statement.payload())
        return await self.request({"op": "batch", "statements": payload})

    async def exec(self, sql: str) -> object:
        """Execute migration SQL only; application adapters use prepare/batch."""
        sql = re.sub(r"--[^\n]*", "", sql).replace("\n", " ")
        return await self.request({"op": "exec", "sql": sql})

    async def migrate(self) -> None:
        directory = Path(__file__).resolve().parents[1] / "migrations"
        migrations = sorted(directory.glob("*.sql"))
        if not migrations:
            raise D1BindingError("No D1 migrations found")
        await self.exec(
            "CREATE TABLE IF NOT EXISTS d1_migrations "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, "
            "applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL);"
        )
        for migration in migrations:
            existing = (
                await self.prepare("SELECT name FROM d1_migrations WHERE name=?")
                .bind(migration.name)
                .first()
            )
            if existing is None:
                await self.exec(migration.read_text())
                await (
                    self.prepare("INSERT INTO d1_migrations(name) VALUES (?)")
                    .bind(migration.name)
                    .run()
                )

    async def request(self, payload: dict[str, object]) -> object:
        statement = payload.get("statement")
        if isinstance(statement, dict):
            fields = cast(dict[str, object], statement)
            sql, params = fields.get("sql"), fields.get("params")
            if isinstance(sql, str) and isinstance(params, list):
                self.statements.append((sql, tuple(cast(list[D1Value], params))))
        result = await asyncio.to_thread(self._request, payload)
        self.results.append(result)
        return result

    def usage(self) -> dict[str, int]:
        """Successful response metadata only; excludes unreported failed operations."""
        totals = {"rows_read": 0, "rows_written": 0, "max_size_after": 0}
        for response in self.results:
            entries = (
                cast(list[object], response)
                if isinstance(response, list)
                else [response]
            )
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                meta = cast(dict[str, object], entry).get("meta")
                if not isinstance(meta, dict):
                    continue
                fields = cast(dict[str, object], meta)
                for name in ("rows_read", "rows_written"):
                    value = fields.get(name)
                    if isinstance(value, int):
                        totals[name] += value
                size = fields.get("size_after")
                if isinstance(size, int):
                    totals["max_size_after"] = max(totals["max_size_after"], size)
        return totals

    def _request(self, payload: dict[str, object]) -> object:
        if not self.url:
            raise D1BindingError("D1 bridge is not running")
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload, allow_nan=False).encode(),
            headers={"Content-Type": "application/json"},
        )
        # Loopback only: never send this test transport through an outbound proxy.
        client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with client.open(request, timeout=30) as response:
                value: object = json.load(response)
        except urllib.error.HTTPError as error:
            diagnostic = error.read(8192).decode(errors="replace")
            raise D1BindingError(
                f"Local D1 rejected operation: {diagnostic}"
            ) from error
        except (urllib.error.URLError, OSError) as error:
            raise D1BindingError(
                "Local D1 operation failed; commit outcome may be unknown"
            ) from error
        if not isinstance(value, dict) or "result" not in value:
            raise D1BindingError("Invalid local D1 result")
        return cast(dict[str, object], value)["result"]

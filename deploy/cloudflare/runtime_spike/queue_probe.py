"""Queue probe shared by the real Worker handler and observable unit checks."""

import inspect
from typing import cast

from bindings import Database, Message


async def process_spike_message(message: Message, database: Database) -> None:
    result = message.ack()
    assert not inspect.isawaitable(result)
    body = message.body
    assert isinstance(body, dict)
    marker = cast(dict[str, object], body).get("marker")
    assert isinstance(marker, str)
    await (
        database.prepare("INSERT INTO spike_events (marker, ack_sync) VALUES (?, 1)")
        .bind(marker)
        .run()
    )
    if marker.startswith("fail-"):
        raise RuntimeError("intentional failure after ack")

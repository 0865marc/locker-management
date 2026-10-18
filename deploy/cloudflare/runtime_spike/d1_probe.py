"""Positive/negative controls for the native D1 batch experiment."""

import json

from bindings import Database, Statement

INSERT_CELL = "INSERT INTO spike_cells (id, value) VALUES (?, ?)"
EXPECTED_CHECK = "CHECK constraint failed: spike_value_nonnegative"


def cell_statements(database: Database, middle_value: int) -> list[Statement]:
    return [
        database.prepare(INSERT_CELL).bind("rollback-first", 1),
        database.prepare(INSERT_CELL).bind("rollback-middle", middle_value),
        database.prepare(INSERT_CELL).bind("rollback-last", 3),
    ]


async def verify_d1_batch(database: Database) -> dict[str, object]:
    await database.prepare("DELETE FROM spike_cells").run()
    # A valid batch must actually commit all three prepared/bound statements.
    # API/bridge errors or first-statement failures must fail this control.
    await database.batch(cell_statements(database, 2))
    positive = await database.prepare(
        "SELECT COUNT(*) AS n, SUM(value) AS total FROM spike_cells"
    ).first()
    assert positive is not None and positive["n"] == 3 and positive["total"] == 6
    await database.prepare("DELETE FROM spike_cells").run()
    # Prepare/bind outside the exception handler: preparation errors cannot
    # masquerade as an expected execution-time constraint failure.
    negative = cell_statements(database, -1)
    try:
        await database.batch(negative)
    except Exception as error:
        if EXPECTED_CHECK not in str(error):
            raise
    else:
        raise AssertionError("D1 accepted the intentionally invalid middle statement")
    row = await database.prepare("SELECT COUNT(*) AS n FROM spike_cells").first()
    assert row is not None and row["n"] == 0
    payload = json.dumps([{"id": f"cell-{n}", "value": n} for n in range(1000)])
    await database.batch(
        [
            database.prepare(
                "INSERT INTO spike_cells (id, value) "
                "SELECT json_extract(value, '$.id'), json_extract(value, '$.value') "
                "FROM json_each(?)"
            ).bind(payload),
        ]
    )
    row = await database.prepare("SELECT COUNT(*) AS n FROM spike_cells").first()
    assert row is not None and row["n"] == 1000
    return {
        "positive_batch_count": positive["n"],
        "expected_check": "spike_value_nonnegative",
        "rollback": True,
        "json_each_count": row["n"],
        "json_bytes": len(payload),
    }

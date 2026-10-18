"""Bounded experiment, not the production Cloudflare composition root."""

import asyncio
import importlib
import json
import sys
from time import perf_counter
from typing import cast
from uuid import UUID

from bindings import Environment, MessageBatch, NativeResponse
from d1_probe import verify_d1_batch
from event_context import (
    EventContext,
    ProbeEnvironment,
    current_environment,
    verify_context_cleanup,
)
from fastapi import FastAPI, Request
from import_clock import STARTED, elapsed_ms
from pydantic import BaseModel, ValidationError
from queue_probe import process_spike_message
from workers import Request as WorkerRequest
from workers import WorkerEntrypoint, asgi

from adapters.http.deliveries.schemas import DeliveryResponse
from adapters.http.lockers.schemas import (
    CompartmentResponse,
    CreateLocker,
    DimensionsInput,
    LockerResponse,
)
from adapters.http.quotations.schemas import QuotationResponse
from adapters.http.returns.schemas import ReturnResponse

# Import the actual shared use cases, without the PostgreSQL composition roots.
for _module in (
    "application.deliveries.use_cases",
    "application.returns.use_cases",
    "application.lockers.use_cases",
    "application.quotations.use_cases",
    "application.quotations.comparison",
):
    importlib.import_module(_module)

app = FastAPI(title="Workers feasibility experiment")
APP_BUILDS = 1


contextual_app = EventContext(app)


def schema_title(model: type[BaseModel]) -> str:
    title: object = model.model_json_schema().get("title")
    assert isinstance(title, str)
    return title


@app.get("/")
async def health() -> dict[str, object]:
    env = current_environment.get()
    forbidden = [
        name
        for name in ("main", "sqlmodel", "asyncpg", "aio_pika", "alembic")
        if name in sys.modules
    ]
    return {
        "status": "ok",
        "label": env.LABEL,
        "app_builds": APP_BUILDS,
        "python": sys.version,
        "import_wall_ms": IMPORT_WALL_MS,
        "import_wall_ms_unavailable_reason": IMPORT_UNAVAILABLE_REASON,
        "timing_source": "runtime perf_counter delta; not CPU",
        "forbidden_imports": forbidden,
        "schemas": [
            schema_title(DeliveryResponse),
            schema_title(ReturnResponse),
            schema_title(QuotationResponse),
            schema_title(LockerResponse),
        ],
    }


@app.post("/validate")
async def validate(body: CreateLocker) -> CreateLocker:
    return body


@app.get("/probe")
async def probe(request: Request) -> dict[str, str]:
    initial = current_environment.get()
    await asyncio.sleep(0.005)
    assert current_environment.get() is initial
    if request.query_params.get("fail") == "yes":
        raise ValueError("intentional context cleanup probe")
    return {"label": initial.LABEL}


@app.get("/context-check")
async def context_check() -> dict[str, object]:
    outer = current_environment.get()
    await verify_context_cleanup(outer)

    async def call(label: str, fail: bool = False) -> tuple[int, str]:
        environment = ProbeEnvironment(outer.DB, outer.QUOTATIONS, label)
        url = "https://runtime.invalid/probe" + ("?fail=yes" if fail else "")
        response: NativeResponse = await asgi.fetch(
            contextual_app, WorkerRequest(url), environment
        )
        return response.status, await response.text()

    values = await asyncio.gather(call("A"), call("B"), call("C", fail=True))
    assert values[0][0] == 200 and json.loads(values[0][1]) == {"label": "A"}
    assert values[1][0] == 200 and json.loads(values[1][1]) == {"label": "B"}
    # FastAPI emits the 500 before rethrowing. The official ASGI adapter returns
    # that completed response rather than propagating the handler exception.
    assert values[2][0] == 500
    assert current_environment.get() is outer
    again = await call("D")
    assert again[0] == 200 and json.loads(again[1]) == {"label": "D"}
    return {"isolated": True, "exception_reset": True, "app_builds": APP_BUILDS}


@app.post("/d1-check")
async def d1_check() -> dict[str, object]:
    return await verify_d1_batch(current_environment.get().DB)


@app.post("/publish/{marker}")
async def publish(marker: str) -> dict[str, object]:
    await current_environment.get().QUOTATIONS.send({"marker": marker})
    return {"confirmed": True, "marker": marker}


@app.get("/queue-events/{marker}")
async def queue_events(marker: str) -> dict[str, object]:
    row = (
        await current_environment.get()
        .DB.prepare(
            "SELECT COUNT(*) AS n, MIN(ack_sync) AS ack_sync "
            "FROM spike_events WHERE marker = ?"
        )
        .bind(marker)
        .first()
    )
    assert row is not None
    return row


@app.get("/benchmark/{count}")
async def benchmark(count: int) -> dict[str, object]:
    assert count in (1, 1000, 2000)
    dimensions = {"width_mm": 100, "height_mm": 100, "depth_mm": 100}
    payload = json.dumps(
        {
            "location_id": "runtime-spike",
            "compartments": [
                {"quantity": 1, "dimensions": dimensions} for _ in range(count)
            ],
        }
    )
    started = perf_counter()
    if count <= 1000:
        request = CreateLocker.model_validate_json(payload)
        assert sum(batch.quantity for batch in request.compartments) == count
    else:
        try:
            CreateLocker.model_validate_json(payload)
        except ValidationError:
            pass
        else:
            raise AssertionError("2000 new cells must be rejected")
    validation_ms, validation_reason = elapsed_ms(started, perf_counter())
    started = perf_counter()
    response = LockerResponse(
        id=UUID(int=1),
        location_id="runtime-spike",
        address=None,
        coordinates=None,
        active=True,
        compartment_count=count,
        compartments=[
            CompartmentResponse(
                id=UUID(int=n + 2),
                dimensions=DimensionsInput(**dimensions),
                enabled=True,
                occupied=False,
            )
            for n in range(count)
        ],
    )
    construction_ms, construction_reason = elapsed_ms(started, perf_counter())
    started = perf_counter()
    serialized = response.model_dump_json()
    serialization_ms, serialization_reason = elapsed_ms(started, perf_counter())
    return {
        "count": count,
        "timing_source": "runtime perf_counter delta; not CPU",
        "validation_wall_ms": validation_ms,
        "validation_wall_ms_unavailable_reason": validation_reason,
        "response_construction_wall_ms": construction_ms,
        "response_construction_wall_ms_unavailable_reason": construction_reason,
        "serialization_wall_ms": serialization_ms,
        "serialization_wall_ms_unavailable_reason": serialization_reason,
        "request_bytes": len(payload),
        "response_bytes": len(serialized),
        "app_builds": APP_BUILDS,
    }


IMPORT_WALL_MS, IMPORT_UNAVAILABLE_REASON = elapsed_ms(STARTED, perf_counter())
# A missing ContextVar value here proves import never needed an event binding.
try:
    current_environment.get()
except LookupError:
    pass
else:
    raise AssertionError("binding unexpectedly available during import")


class Default(WorkerEntrypoint):
    async def fetch(self, request: WorkerRequest) -> object:
        return await asgi.fetch(contextual_app, request, self.env, self.ctx)

    async def queue(self, batch: MessageBatch) -> None:
        environment = cast(Environment, self.env)
        token = current_environment.set(environment)
        try:
            for message in batch.messages:
                await process_spike_message(message, environment.DB)
        finally:
            current_environment.reset(token)

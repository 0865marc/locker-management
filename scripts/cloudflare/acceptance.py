"""Bounded HTTP acceptance campaign. Remote CPU/quota evidence is collected separately.

This script writes only through the explicitly supplied API URL. It never creates
Cloudflare resources, changes plans, deletes data or deploys code. Use a fresh,
authorized test installation; the created fixture data intentionally remains.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
import urllib.error
import urllib.request
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol, cast
from uuid import uuid4

DIMENSIONS = {"width_mm": 100, "height_mm": 100, "depth_mm": 100}
QUOTATION = {
    "origin_country_code": "ES",
    "origin_postal_code": "28001",
    "destination_country_code": "ES",
    "destination_postal_code": "08001",
    "weight_grams": 1000,
    "dimensions": DIMENSIONS,
}
# Conservative ceilings, not claims of measured consumption or Free availability.
CAMPAIGN_BUDGET = {
    "lockers": 10,
    "compartments": 2090,
    "deliveries": 100,
    "returns": 100,
    "quotations": 30,
    "max_http_requests": 1000,
    "max_queue_messages_sent": 30,
    "max_expected_queue_operations": 90,
    "conservative_d1_rows_written": 50000,
}


class Request(Protocol):
    async def __call__(
        self, method: str, path: str, body: object | None = None
    ) -> tuple[int, object]: ...


def record(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise AssertionError("Expected a JSON object")
    return cast(dict[str, object], value)


def identifier(value: object) -> str:
    key = record(value).get("id")
    if not isinstance(key, str):
        raise AssertionError("Missing response identifier")
    return key


def utc_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise AssertionError("Missing UTC timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise AssertionError("Timestamp must be UTC")
    return parsed


@dataclass
class Campaign:
    request: Request
    max_requests: int = 1000
    after_quotes: Callable[[], Awaitable[None]] | None = None
    attempts: int = 0
    samples: list[dict[str, object]] = field(default_factory=list[dict[str, object]])

    def __post_init__(self) -> None:
        if type(self.max_requests) is not int or not 1 <= self.max_requests <= 1000:
            raise ValueError("Campaign max_requests must be between 1 and 1000")

    async def call(
        self,
        method: str,
        path: str,
        body: object | None = None,
        *,
        expected: int | tuple[int, ...] = 200,
    ) -> object:
        if self.attempts >= self.max_requests:
            raise RuntimeError(
                "Campaign request budget reached; auxiliary traffic stopped"
            )
        self.attempts += 1
        started = time.perf_counter()
        status, value = await self.request(method, path, body)
        self.samples.append(
            {
                "method": method,
                "path": path,
                "status": status,
                "wall_ms": (time.perf_counter() - started) * 1000,
            }
        )
        if status not in ((expected,) if isinstance(expected, int) else expected):
            raise AssertionError(
                f"{method} {path}: expected {expected}, received {status}"
            )
        return value

    async def run(self) -> dict[str, object]:
        run_id = uuid4().hex
        await self.call("GET", "/docs")
        await self.call("GET", "/openapi.json")
        lockers: list[str] = []
        for index in range(10):
            created = await self.call(
                "POST",
                "/lockers",
                {
                    "location_id": f"acceptance-{run_id}-{index}",
                    "compartments": [
                        {
                            "quantity": 1000 if index == 0 else 10,
                            "dimensions": DIMENSIONS,
                        }
                    ],
                },
                expected=201,
            )
            lockers.append(identifier(created))
        large = lockers[0]
        expanded = await self.call(
            "POST",
            f"/lockers/{large}/compartments",
            {
                "compartments": [{"quantity": 1000, "dimensions": DIMENSIONS}],
            },
            expected=201,
        )
        expanded_cells = record(expanded).get("compartments")
        if (
            record(expanded).get("compartment_count") != 2000
            or not isinstance(expanded_cells, list)
            or len(cast(list[object], expanded_cells)) != 2000
        ):
            raise AssertionError("Accumulated capacity was truncated")
        await self.call(
            "POST",
            f"/lockers/{large}/compartments",
            {
                "compartments": [{"quantity": 1001, "dimensions": DIMENSIONS}],
            },
            expected=422,
        )
        for key in lockers:
            await self.call("GET", f"/lockers/{key}")
        all_lockers = await self.call("GET", "/lockers")
        if not isinstance(all_lockers, list) or {
            identifier(value) for value in cast(list[object], all_lockers)
        } != set(lockers):
            raise AssertionError("Locker list is incomplete")
        await self.call(
            "GET",
            "/lockers/availability?location_id="
            f"acceptance-{run_id}-0&width_mm=100&height_mm=100&depth_mm=100",
        )
        small = record(await self.call("GET", f"/lockers/{lockers[1]}"))
        compartments = small.get("compartments")
        if not isinstance(compartments, list) or not compartments:
            raise AssertionError("Missing compartments")
        cell = identifier(cast(list[object], compartments)[0])
        await self.call("PATCH", f"/lockers/{lockers[1]}", {"active": False})
        await self.call("PATCH", f"/lockers/{lockers[1]}", {"active": True})
        await self.call(
            "PATCH", f"/lockers/{lockers[1]}/compartments/{cell}", {"enabled": False}
        )
        await self.call(
            "DELETE", f"/lockers/{lockers[1]}/compartments/{cell}", expected=204
        )
        # Four ordinary requests execute concurrently, independently of CAS races.
        await asyncio.gather(
            *(self.call("GET", f"/lockers/{key}") for key in lockers[:4])
        )
        # Preserve exact integer volume ordering and UUID tie-breaking near max axes.
        maximum = 2147483647
        precision_locker = record(await self.call("GET", f"/lockers/{lockers[3]}"))
        precision_cells = precision_locker.get("compartments")
        if not isinstance(precision_cells, list):
            raise AssertionError("Missing precision compartments")
        candidates: list[tuple[int, str]] = []
        precision_dimensions = (
            (maximum, maximum, maximum),
            (maximum, maximum, maximum - 2),
            (maximum, maximum - 1, maximum - 1),
            (maximum, maximum, maximum - 2),
        )
        maximum_cell = ""
        for index, value in enumerate(cast(list[object], precision_cells)):
            cell_id = identifier(value)
            if index < 4:
                width, height, depth = precision_dimensions[index]
                dimensions = {"width_mm": width, "height_mm": height, "depth_mm": depth}
                changed = record(
                    await self.call(
                        "PATCH",
                        f"/lockers/{lockers[3]}/compartments/{cell_id}",
                        {"dimensions": dimensions},
                    )
                )
                if changed.get("dimensions") != dimensions:
                    raise AssertionError("Maximum dimensions lost precision")
                candidates.append((width * height * depth, cell_id))
                if index == 0:
                    maximum_cell = cell_id
            else:
                await self.call(
                    "PATCH",
                    f"/lockers/{lockers[3]}/compartments/{cell_id}",
                    {"enabled": False},
                )
        exact_cell = min(candidates)[1]
        # A shared final cell must admit exactly one concurrent reception.
        racing = record(await self.call("GET", f"/lockers/{lockers[2]}"))
        racing_cells = racing.get("compartments")
        if not isinstance(racing_cells, list):
            raise AssertionError("Missing race compartments")
        for cell_value in cast(list[object], racing_cells)[1:]:
            await self.call(
                "PATCH",
                f"/lockers/{lockers[2]}/compartments/{identifier(cell_value)}",
                {"enabled": False},
            )
        race_start = len(self.samples)
        race_results = await asyncio.gather(
            *(
                self.call(
                    "POST",
                    "/deliveries",
                    {
                        "tracking_number": f"{run_id}-race-{index}",
                        "carrier_code": "fixture",
                        "recipient_name": "Acceptance",
                        "locker_id": lockers[2],
                        "parcel_dimensions": DIMENSIONS,
                    },
                    expected=(201, 409),
                )
                for index in range(2)
            )
        )
        if sorted(
            sample["status"]
            for sample in self.samples[race_start:]
            if isinstance(sample["status"], int)
        ) != [201, 409]:
            raise AssertionError("Last-cell race did not produce exactly one winner")
        winner = next(value for value in race_results if "id" in record(value))
        winner = await self.call("POST", f"/deliveries/{identifier(winner)}/collect")
        for kind in ("deliveries", "returns"):
            created_ids: set[str] = (
                {identifier(winner)} if kind == "deliveries" else set()
            )
            expected_rows: dict[str, object] = (
                {identifier(winner): winner} if kind == "deliveries" else {}
            )
            for index in range(1 if kind == "deliveries" else 0, 100):
                payload: dict[str, object] = {
                    "tracking_number": f"{run_id}-{kind}-{index}",
                    "carrier_code": "fixture",
                }
                if index % 2 == 0:
                    payload.update(
                        {"locker_id": large, "parcel_dimensions": DIMENSIONS}
                    )
                if kind == "deliveries":
                    payload["recipient_name"] = "Acceptance"
                    payload["pickup_deadline_at"] = "2020-01-01T12:00:00.123456+02:00"
                    if index in (2, 4):
                        payload["locker_id"] = lockers[3]
                        payload["parcel_dimensions"] = (
                            {
                                "width_mm": maximum,
                                "height_mm": maximum,
                                "depth_mm": maximum,
                            }
                            if index == 4
                            else DIMENSIONS
                        )
                created = await self.call("POST", f"/{kind}", payload, expected=201)
                key = identifier(created)
                fields = record(created)
                received_at = fields.get("received_at")
                utc_timestamp(received_at)
                if kind == "deliveries":
                    if (
                        fields.get("pickup_deadline_at")
                        != "2020-01-01T10:00:00.123456Z"
                    ):
                        raise AssertionError("UTC microseconds were not preserved")
                    if index in (2, 4) and fields.get("compartment_id") != (
                        exact_cell if index == 2 else maximum_cell
                    ):
                        raise AssertionError(
                            "Exact volume/UUID or maximum-axis selection changed"
                        )
                created_ids.add(key)
                if index % 4 in (0, 1):
                    action = (
                        ("collect" if (index // 4) % 2 == 0 else "return-to-carrier")
                        if kind == "deliveries"
                        else "hand-over"
                    )
                    created = await self.call("POST", f"/{kind}/{key}/{action}")
                    fields = record(created)
                    if fields.get("received_at") != received_at:
                        raise AssertionError("Exit changed reception timestamp")
                    utc_timestamp(
                        fields.get(
                            {
                                "collect": "collected_at",
                                "return-to-carrier": "returned_to_carrier_at",
                                "hand-over": "handed_over_at",
                            }[action]
                        )
                    )
                    if index == 4:
                        await self.call("POST", f"/{kind}/{key}/{action}", expected=409)
                expected_rows[key] = created
            values = await self.call("GET", f"/{kind}")
            if not isinstance(values, list):
                raise AssertionError("Expected complete parcel list")
            rows = [record(value) for value in cast(list[object], values)]
            if len(rows) != 100 or {identifier(row) for row in rows} != created_ids:
                raise AssertionError("Parcel list omitted created identifiers")
            if any(row != expected_rows[identifier(row)] for row in rows):
                raise AssertionError(
                    "Persisted parcel snapshots changed or lost microseconds"
                )
            pending_status = (
                "AWAITING_PICKUP" if kind == "deliveries" else "AWAITING_CARRIER"
            )
            categories = {
                (assigned, pending): 0
                for assigned in (False, True)
                for pending in (False, True)
            }
            for row in rows:
                assigned = row.get("locker_id") is not None
                pending_state = row.get("status") == pending_status
                categories[assigned, pending_state] += 1
            if set(categories.values()) != {25}:
                raise AssertionError(
                    "Parcel fixture must include 25 of each pending/terminal and assigned/unassigned combination"
                )
        quotes: list[str] = []
        for _ in range(30):
            quotes.append(
                identifier(
                    await self.call("POST", "/quotations", QUOTATION, expected=202)
                )
            )
        if self.after_quotes is not None:
            await self.after_quotes()
        pending = set(quotes)
        provider_statuses: dict[str, int] = {}
        deadline = time.monotonic() + 1800
        while pending:
            for key in tuple(pending):
                result = record(await self.call("GET", f"/quotations/{key}"))
                if identifier(result) != key or result.get("request") != QUOTATION:
                    raise AssertionError(
                        "Quotation snapshot lost its identity or request"
                    )
                utc_timestamp(result.get("created_at"))
                status = result.get("status")
                if status not in ("PENDING", "PROCESSING", "COMPLETED", "FAILED"):
                    raise AssertionError("Unknown quotation status")
                providers = result.get("results")
                if status in ("PENDING", "PROCESSING") and providers != []:
                    raise AssertionError("Quotation exposed partial provider results")
                if status == "COMPLETED":
                    utc_timestamp(result.get("finished_at"))
                    if result.get("process_error_code") is not None:
                        raise AssertionError(
                            "Completed quotation retained a process error"
                        )
                    if (
                        not isinstance(providers, list)
                        or len(cast(list[object], providers)) != 3
                    ):
                        raise AssertionError(
                            "Completed quotation must contain all three providers"
                        )
                    codes: set[str] = set()
                    for provider in cast(list[object], providers):
                        fields = record(provider)
                        code = fields.get("provider_code")
                        if not isinstance(code, str) or code in codes:
                            raise AssertionError("Invalid or duplicate provider code")
                        codes.add(code)
                        provider_status = fields.get("status")
                        offers = fields.get("offers")
                        error = fields.get("error_code")
                        if provider_status == "QUOTED":
                            if (
                                error is not None
                                or not isinstance(offers, list)
                                or not offers
                            ):
                                raise AssertionError("Invalid quoted provider snapshot")
                            for offer in cast(list[object], offers):
                                values = record(offer)
                                price = values.get("price_cents")
                                minimum, maximum = (
                                    values.get("transit_days_min"),
                                    values.get("transit_days_max"),
                                )
                                if (
                                    not isinstance(values.get("service_code"), str)
                                    or not values.get("service_code")
                                    or values.get("currency") != "EUR"
                                    or type(price) is not int
                                    or price <= 0
                                    or type(minimum) is not int
                                    or minimum <= 0
                                    or type(maximum) is not int
                                    or maximum < minimum
                                ):
                                    raise AssertionError(
                                        "Invalid shipping offer snapshot"
                                    )
                        elif provider_status == "NOT_COVERED":
                            if offers != [] or error is not None:
                                raise AssertionError(
                                    "Invalid uncovered provider snapshot"
                                )
                        elif provider_status == "FAILED":
                            if offers != [] or error not in (
                                "PROVIDER_ERROR",
                                "PROVIDER_TIMEOUT",
                            ):
                                raise AssertionError("Invalid failed provider snapshot")
                        else:
                            raise AssertionError("Unknown provider status")
                        assert isinstance(provider_status, str)
                        provider_statuses[provider_status] = (
                            provider_statuses.get(provider_status, 0) + 1
                        )
                    if codes != {"sim-economy", "sim-standard", "sim-express"}:
                        raise AssertionError("Quotation omitted configured providers")
                    pending.remove(key)
                elif status == "FAILED":
                    raise AssertionError("Quotation processing failed")
            if pending:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Quotation campaign exceeded its time budget")
                await asyncio.sleep(2)
        return {
            "scope": "HTTP campaign; wall time is not CPU",
            "budget": CAMPAIGN_BUDGET,
            "samples": self.samples,
            "observed_provider_statuses": provider_statuses,
            "remote_cpu_ms": None,
            "remote_d1_rows": None,
            "remote_queue_operations": None,
            "free_acceptance": "pending platform metrics and quota verification",
        }


class HttpRequest:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def __call__(
        self, method: str, path: str, body: object | None = None
    ) -> tuple[int, object]:
        return await asyncio.to_thread(self._request, method, path, body)

    def _request(
        self, method: str, path: str, body: object | None
    ) -> tuple[int, object]:
        request = urllib.request.Request(
            self.base_url + path,
            method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            client = (
                urllib.request.build_opener(urllib.request.ProxyHandler({}))
                if self.base_url.startswith("http://127.0.0.1:")
                else urllib.request.build_opener()
            )
            response = client.open(request, timeout=60)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            data = response.read()
            value: object = (
                json.loads(data)
                if data and "json" in response.headers.get("Content-Type", "")
                else None
            )
            status: object = response.status
            if not isinstance(status, int):
                raise RuntimeError("Missing HTTP status")
            return status, value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--max-requests", type=int, default=1000)
    options = parser.parse_args()
    base_url: str = options.base_url
    if not base_url.startswith(("http://127.0.0.1:", "https://")):
        parser.error("Use an HTTPS test installation or a loopback HTTP URL")
    result = asyncio.run(Campaign(HttpRequest(base_url), options.max_requests).run())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

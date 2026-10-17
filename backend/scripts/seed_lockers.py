"""Manually create synthetic lockers through the public API, without retries."""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
from dataclasses import dataclass
from http.client import HTTPException
from ipaddress import ip_address
from pathlib import Path
from typing import TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

BOUNDARY_PATH = Path(__file__).with_name("data") / "spain.geojson"
REQUEST_TIMEOUT = 10
MAX_RESPONSE_BYTES = 1024 * 1024

Point = tuple[float, float]  # GeoJSON order: longitude, latitude.
Ring = tuple[Point, ...]


@dataclass(frozen=True)
class Polygon:
    rings: tuple[Ring, ...]
    bounds: tuple[float, float, float, float]


class CoordinatesPayload(TypedDict):
    latitude: float
    longitude: float


class DimensionsPayload(TypedDict):
    width_mm: int
    height_mm: int
    depth_mm: int


class BatchPayload(TypedDict):
    quantity: int
    dimensions: DimensionsPayload
    enabled: bool


class LockerPayload(TypedDict):
    location_id: str
    address: None
    coordinates: CoordinatesPayload
    active: bool
    compartments: list[BatchPayload]


def load_boundary(path: Path = BOUNDARY_PATH) -> tuple[Polygon, ...]:
    """Load the bundled land geometry before any request can be made."""
    geometry: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(geometry, dict) or geometry.get("type") != "MultiPolygon":
        raise ValueError("La geografía debe ser un MultiPolygon GeoJSON")
    coordinates: object = geometry.get("coordinates")
    if not isinstance(coordinates, list) or not coordinates:
        raise ValueError("La geografía no contiene polígonos")
    polygons: list[Polygon] = []
    for polygon in coordinates:
        if not isinstance(polygon, list) or not polygon:
            raise ValueError("Polígono vacío o inválido")
        rings: list[Ring] = []
        for ring in polygon:
            if not isinstance(ring, list) or len(ring) < 4:
                raise ValueError("Anillo inválido")
            points: list[Point] = []
            for point in ring:
                if (
                    not isinstance(point, list)
                    or len(point) != 2
                    or any(type(value) not in (int, float) for value in point)
                ):
                    raise ValueError("Coordenada inválida")
                longitude, latitude = float(point[0]), float(point[1])
                if (
                    not math.isfinite(longitude)
                    or not math.isfinite(latitude)
                    or not -180 <= longitude <= 180
                    or not -90 <= latitude <= 90
                ):
                    raise ValueError("Coordenada fuera de rango")
                points.append((longitude, latitude))
            if points[0] != points[-1]:
                raise ValueError("Anillo sin cerrar")
            rings.append(tuple(points))
        shell = rings[0]
        bounds = (
            min(point[0] for point in shell),
            min(point[1] for point in shell),
            max(point[0] for point in shell),
            max(point[1] for point in shell),
        )
        if bounds[0] == bounds[2] or bounds[1] == bounds[3]:
            raise ValueError("Polígono sin superficie")
        polygons.append(Polygon(tuple(rings), bounds))
    return tuple(polygons)


def ring_location(point: Point, ring: Ring) -> int:
    """Return 1 inside, 0 outside or -1 on the edge (ray casting)."""
    longitude, latitude = point
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        cross = (longitude - x1) * (y2 - y1) - (latitude - y1) * (x2 - x1)
        if (
            abs(cross) < 1e-12
            and min(x1, x2) <= longitude <= max(x1, x2)
            and min(y1, y2) <= latitude <= max(y1, y2)
        ):
            return -1
        if (y1 > latitude) != (y2 > latitude):
            intersection = x1 + (latitude - y1) * (x2 - x1) / (y2 - y1)
            if longitude < intersection:
                inside = not inside
    return 1 if inside else 0


def on_land(point: Point, polygons: tuple[Polygon, ...]) -> bool:
    """Accept only shell interiors, excluding holes and boundary points."""
    longitude, latitude = point
    for polygon in polygons:
        west, south, east, north = polygon.bounds
        if not (west < longitude < east and south < latitude < north):
            continue
        if ring_location(point, polygon.rings[0]) == 1 and all(
            ring_location(point, hole) == 0 for hole in polygon.rings[1:]
        ):
            return True
    return False


def generate_payloads(
    count: int, seed: int, polygons: tuple[Polygon, ...]
) -> list[LockerPayload]:
    if count <= 0 or not polygons:
        raise ValueError("La cantidad y la geografía deben ser válidas")
    generator = random.Random(seed)
    west = min(polygon.bounds[0] for polygon in polygons)
    south = min(polygon.bounds[1] for polygon in polygons)
    east = max(polygon.bounds[2] for polygon in polygons)
    north = max(polygon.bounds[3] for polygon in polygons)
    payloads: list[LockerPayload] = []
    # Finite rejection budget also prevents corrupt geometry from hanging a run.
    for _ in range(max(10000, count * 1000)):
        point = (generator.uniform(west, east), generator.uniform(south, north))
        rounded = (round(point[0], 6), round(point[1], 6))
        if not on_land(point, polygons) or not on_land(rounded, polygons):
            continue
        payloads.append(
            {
                "location_id": f"DEMO-{seed}-{len(payloads) + 1}",
                "address": None,
                "active": True,
                "coordinates": {"longitude": rounded[0], "latitude": rounded[1]},
                "compartments": [
                    {
                        "quantity": 6,
                        "enabled": True,
                        "dimensions": {
                            "width_mm": 400,
                            "height_mm": 400,
                            "depth_mm": 600,
                        },
                    }
                ],
            }
        )
        if len(payloads) == count:
            return payloads
    raise ValueError("No se pudieron generar todos los puntos terrestres")


def positive_integer(value: str) -> int:
    count = int(value)
    if count <= 0:
        raise argparse.ArgumentTypeError("La cantidad debe ser positiva")
    return count


def api_base_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or "?" in value
            or "#" in value
            or "*" in value
            or "\\" in value
            or any(character.isspace() for character in value)
            or parsed.netloc.endswith(":")
            or not re.fullmatch(
                r"(?:[a-zA-Z0-9.-]+|\[[0-9a-fA-F:.]+\])(?::[0-9]+)?",
                parsed.netloc,
            )
        ):
            raise ValueError
        _ = parsed.port
        host = parsed.hostname
        if ":" in host or re.fullmatch(r"[0-9.]+", host):
            ip_address(host)
        elif len(host) > 253 or not re.fullmatch(
            r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
            r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*",
            host,
        ):
            raise ValueError
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "La URL API debe ser HTTP(S), sin credenciales, query ni fragmento"
        ) from error
    return value.rstrip("/")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> None:
        return None


def create_locker(base_url: str, payload: LockerPayload) -> None:
    request = Request(
        f"{base_url}/lockers",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with build_opener(NoRedirect()).open(request, timeout=REQUEST_TIMEOUT) as response:
        if response.status != 201:
            raise ValueError(f"HTTP {response.status}: creación no confirmada")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("Respuesta demasiado grande; creación no confirmada")
        body: object = json.loads(raw)
        if not isinstance(body, dict) or not isinstance(body.get("id"), str):
            raise ValueError("Respuesta sin UUID; creación no confirmada")
        UUID(body["id"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=positive_integer, default=250)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--base-url", type=api_base_url, default="http://127.0.0.1:8000"
    )
    parser.add_argument("--dry-run", action="store_true")
    options = parser.parse_args(argv)
    try:
        payloads = generate_payloads(options.count, options.seed, load_boundary())
    except (OSError, ValueError) as error:
        print(f"Error antes de escribir: {error}", file=sys.stderr)
        return 1
    if options.dry_run:
        print(json.dumps(payloads, ensure_ascii=False))
        return 0

    print(
        f"Datos sintéticos: se añadirán {len(payloads)} lockers; "
        "otra ejecución añade registros nuevos, aunque repita la semilla.",
        file=sys.stderr,
    )
    confirmed = 0
    for index, payload in enumerate(payloads, start=1):
        try:
            create_locker(options.base_url, payload)
        except (OSError, URLError, HTTPError, HTTPException, ValueError) as error:
            print(
                f"Confirmados: {confirmed}/{len(payloads)}. "
                f"Fallo en elemento {index} ({payload['location_id']}): {error}. "
                "Resultado de este elemento no confirmado; puede haberse creado. "
                "No se reintenta ni se borra ningún registro. Revisa la API.",
                file=sys.stderr,
            )
            return 1
        confirmed += 1
    print(f"Confirmados: {confirmed}/{len(payloads)}.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

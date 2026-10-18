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

CATALOGUE_PATH = Path(__file__).with_name("data") / "spain-addresses.json"
SNAPSHOT_DATE = "17/10/2026 23:09:30"
SNAPSHOT_SHA256 = "91ee3c584c20563d60f5f9389dec011cef0e3d8a69a2fc89ab9cc5aadbf26f9b"
SOURCE_FIELDS = (
    "IDEESS",
    "IDProvincia",
    "Provincia",
    "Municipio",
    "Localidad",
    "Dirección",
    "C.P.",
    "Latitud",
    "Longitud (WGS84)",
)
STREET_PATTERN = re.compile(
    r"((?:CALLE|AVENIDA|PLAZA|PASEO|RONDA|TRAVESIA|TRAVESÍA|CARRER|AVINGUDA|RAMBLA) "
    r"[^,]+),\s*([0-9]+[A-Za-z]?)"
)
REQUEST_TIMEOUT = 10
MAX_RESPONSE_BYTES = 1024 * 1024


class CoordinatesPayload(TypedDict):
    latitude: float
    longitude: float


class AddressPayload(TypedDict):
    country_code: str
    postal_code: str
    province: str
    city: str
    street: str
    street_number: str


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
    address: AddressPayload
    coordinates: CoordinatesPayload
    active: bool
    compartments: list[BatchPayload]


@dataclass(frozen=True)
class CatalogueLocation:
    source_id: str
    source_province_id: str
    source_address: str
    source_latitude: str
    source_longitude: str
    address: AddressPayload
    coordinates: CoordinatesPayload


def source_record(value: object) -> CatalogueLocation:
    """Normalize only complete source records with an explicit street number."""
    if not isinstance(value, dict):
        raise ValueError("Registro del catálogo inválido")
    fields: dict[str, str] = {}
    for key in SOURCE_FIELDS:
        text: object = value.get(key)
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"Campo de catálogo ausente o inválido: {key}")
        fields[key] = text
    identifier, province_id = fields["IDEESS"], fields["IDProvincia"]
    postal_code = fields["C.P."]
    if (
        re.fullmatch(r"[0-9]+", identifier) is None
        or re.fullmatch(r"[0-9]{2}", province_id) is None
        or not 1 <= int(province_id) <= 52
        or re.fullmatch(r"[0-9]{5}", postal_code) is None
        or postal_code[:2] != province_id
    ):
        raise ValueError("Identificador o CP/provincia inválido en el catálogo")
    street = STREET_PATTERN.fullmatch(fields["Dirección"])
    if street is None:
        raise ValueError("La dirección no contiene calle y número inequívocos")
    numbers: list[float] = []
    for name in ("Latitud", "Longitud (WGS84)"):
        text = fields[name]
        if re.fullmatch(r"-?[0-9]+(?:,[0-9]+)?", text) is None:
            raise ValueError("Formato de coordenadas del catálogo inválido")
        number = float(text.replace(",", "."))
        if not math.isfinite(number):
            raise ValueError("Coordenadas del catálogo no finitas")
        numbers.append(number)
    latitude, longitude = numbers
    if not (27 <= latitude <= 44 and -19 <= longitude <= 5):
        raise ValueError("Coordenadas fuera del ámbito español del catálogo")
    return CatalogueLocation(
        identifier,
        province_id,
        fields["Dirección"],
        fields["Latitud"],
        fields["Longitud (WGS84)"],
        {
            "country_code": "ES",
            "postal_code": postal_code,
            "province": fields["Provincia"],
            "city": fields["Localidad"],
            "street": street.group(1),
            "street_number": street.group(2),
        },
        {"latitude": latitude, "longitude": longitude},
    )


def load_catalogue(path: Path = CATALOGUE_PATH) -> tuple[CatalogueLocation, ...]:
    """Validate every record and source version before any HTTP write."""
    catalogue: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(catalogue, dict):
        raise ValueError("Catálogo de direcciones inválido")
    source: object = catalogue.get("source")
    if (
        not isinstance(source, dict)
        or source.get("snapshot_date") != SNAPSHOT_DATE
        or source.get("snapshot_sha256") != SNAPSHOT_SHA256
    ):
        raise ValueError("Versión o procedencia del catálogo inválida")
    records: object = catalogue.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("El catálogo no contiene direcciones")
    locations = tuple(source_record(record) for record in records)
    if len({location.source_id for location in locations}) != len(locations):
        raise ValueError("Identificadores fuente duplicados en el catálogo")
    return locations


def generate_payloads(
    count: int, seed: int, locations: tuple[CatalogueLocation, ...]
) -> list[LockerPayload]:
    if count <= 0 or not locations:
        raise ValueError("La cantidad y el catálogo deben ser válidos")
    generator = random.Random(seed)
    payloads: list[LockerPayload] = []
    while len(payloads) < count:
        cycle = list(locations)
        generator.shuffle(cycle)
        for location in cycle[: count - len(payloads)]:
            payloads.append(
                {
                    "location_id": f"DEMO-{seed}-{len(payloads) + 1}",
                    "address": location.address.copy(),
                    "active": True,
                    "coordinates": location.coordinates.copy(),
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
    return payloads


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
        payloads = generate_payloads(options.count, options.seed, load_catalogue())
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

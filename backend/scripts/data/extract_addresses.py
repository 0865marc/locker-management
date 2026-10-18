"""Reproduce the address catalogue from the pinned, already downloaded snapshot."""

import argparse
import hashlib
import json
from pathlib import Path

from scripts.seed_lockers import (
    CATALOGUE_PATH,
    SNAPSHOT_DATE,
    SNAPSHOT_SHA256,
    SOURCE_FIELDS,
    source_record,
)

MIRROR_COMMIT = "5e9e8770d97ccb882127e6cd4cd60b302fc0a1d2"
MIRROR_URL = (
    "https://raw.githubusercontent.com/ioritzarroyuelos-ai/gasolineras-espana/"
    f"{MIRROR_COMMIT}/public/data/stations.json"
)
OFFICIAL_URL = (
    "https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/"
    "PreciosCarburantes/EstacionesTerrestres/"
)


def extract(snapshot: Path, output: Path) -> int:
    raw = snapshot.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SNAPSHOT_SHA256:
        raise ValueError("El snapshot no coincide con el SHA-256 fijado")
    content: object = json.loads(raw)
    if not isinstance(content, dict) or content.get("Fecha") != SNAPSHOT_DATE:
        raise ValueError("Fecha de snapshot inválida")
    rows: object = content.get("ListaEESSPrecio")
    if not isinstance(rows, list) or len(rows) != 11431:
        raise ValueError("Número de registros del snapshot inesperado")
    records: list[dict[str, object]] = []
    for row in rows:
        try:
            source_record(row)
        except ValueError:
            continue
        if isinstance(row, dict):
            records.append({field: row[field] for field in SOURCE_FIELDS})
    catalogue = {
        "source": {
            "publisher": "Ministerio para la Transición Ecológica y el Reto Demográfico (MITECO)",
            "official_url": OFFICIAL_URL,
            "mirror_url": MIRROR_URL,
            "mirror_commit": MIRROR_COMMIT,
            "snapshot_date": SNAPSHOT_DATE,
            "snapshot_sha256": SNAPSHOT_SHA256,
            "snapshot_bytes": len(raw),
            "snapshot_records": len(rows),
        },
        "records": records,
    }
    output.write_text(
        json.dumps(catalogue, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return len(records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--output", type=Path, default=CATALOGUE_PATH)
    args = parser.parse_args()
    print(f"Registros extraídos: {extract(args.snapshot, args.output)}")

from datetime import datetime, timezone
from uuid import UUID

__all__ = ["CustodyConflictError", "_text", "_optional_text", "_utc", "_uuid", "_exit_at"]


class CustodyConflictError(ValueError):
    """The parcel cannot leave custody in the requested way or at that time."""


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} debe ser un texto no vacío")
    return value.strip()


def _optional_text(value: object, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} debe ser un texto")
    return value.strip() or None


def _utc(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} debe incluir zona horaria")
    return value.astimezone(timezone.utc)


def _uuid(value: object) -> UUID:
    if not isinstance(value, UUID):
        raise ValueError("id debe ser un UUID")
    return value


def _exit_at(at: datetime, received_at: datetime) -> datetime:
    at = _utc(at, "fecha de salida")
    if at < received_at:
        raise CustodyConflictError("La salida no puede ser anterior a la recepción")
    return at

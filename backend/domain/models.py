from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from domain.lockers import Dimensions


class CustodyConflictError(ValueError):
    """The parcel cannot leave custody in the requested way or at that time."""


class DeliveryStatus(str, Enum):
    AWAITING_PICKUP = "AWAITING_PICKUP"
    COLLECTED = "COLLECTED"
    RETURNED_TO_CARRIER = "RETURNED_TO_CARRIER"


class ReturnStatus(str, Enum):
    AWAITING_CARRIER = "AWAITING_CARRIER"
    HANDED_OVER = "HANDED_OVER"


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


def _normalize_common(parcel: "Delivery | Return") -> None:
    for name in ("tracking_number", "carrier_code"):
        object.__setattr__(parcel, name, _text(getattr(parcel, name), name))
    object.__setattr__(parcel, "received_at", _utc(parcel.received_at, "received_at"))
    object.__setattr__(parcel, "id", _uuid(parcel.id))
    values = (parcel.locker_id, parcel.compartment_id, parcel.parcel_dimensions)
    if any(v is not None for v in values):
        if not (isinstance(parcel.locker_id, UUID) and isinstance(parcel.compartment_id, UUID)
                and isinstance(parcel.parcel_dimensions, Dimensions)):
            raise ValueError("La asignación debe estar completa")


def _exit_at(at: datetime, received_at: datetime) -> datetime:
    at = _utc(at, "fecha de salida")
    if at < received_at:
        raise CustodyConflictError("La salida no puede ser anterior a la recepción")
    return at


@dataclass(frozen=True)
class Delivery:
    tracking_number: str
    carrier_code: str
    recipient_name: str
    received_at: datetime
    recipient_phone: str | None = None
    pickup_deadline_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)
    status: DeliveryStatus = DeliveryStatus.AWAITING_PICKUP
    collected_at: datetime | None = None
    returned_to_carrier_at: datetime | None = None

    locker_id: UUID | None = None
    compartment_id: UUID | None = None
    parcel_dimensions: Dimensions | None = None

    def __post_init__(self) -> None:
        _normalize_common(self)
        object.__setattr__(self, "recipient_name", _text(self.recipient_name, "recipient_name"))
        object.__setattr__(self, "recipient_phone", _optional_text(self.recipient_phone, "recipient_phone"))
        object.__setattr__(self, "status", DeliveryStatus(self.status))
        for name in ("pickup_deadline_at", "collected_at", "returned_to_carrier_at"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _utc(value, name))
        expected = {
            DeliveryStatus.AWAITING_PICKUP: (False, False),
            DeliveryStatus.COLLECTED: (True, False),
            DeliveryStatus.RETURNED_TO_CARRIER: (False, True),
        }[self.status]
        if (self.collected_at is not None, self.returned_to_carrier_at is not None) != expected:
            raise ValueError("El estado de Delivery y sus fechas de salida son incompatibles")
        for at in (self.collected_at, self.returned_to_carrier_at):
            if at is not None and at < self.received_at:
                raise ValueError("La salida no puede ser anterior a la recepción")

    def collect(self, at: datetime) -> "Delivery":
        self._require_pending()
        return replace(self, status=DeliveryStatus.COLLECTED, collected_at=_exit_at(at, self.received_at))

    def return_to_carrier(self, at: datetime) -> "Delivery":
        self._require_pending()
        return replace(
            self,
            status=DeliveryStatus.RETURNED_TO_CARRIER,
            returned_to_carrier_at=_exit_at(at, self.received_at),
        )

    def _require_pending(self) -> None:
        if self.status != DeliveryStatus.AWAITING_PICKUP:
            raise CustodyConflictError("El paquete ya ha salido del punto de recogida")


@dataclass(frozen=True)
class Return:
    tracking_number: str
    carrier_code: str
    received_at: datetime
    sender_name: str | None = None
    id: UUID = field(default_factory=uuid4)
    status: ReturnStatus = ReturnStatus.AWAITING_CARRIER
    handed_over_at: datetime | None = None

    locker_id: UUID | None = None
    compartment_id: UUID | None = None
    parcel_dimensions: Dimensions | None = None

    def __post_init__(self) -> None:
        _normalize_common(self)
        object.__setattr__(self, "sender_name", _optional_text(self.sender_name, "sender_name"))
        object.__setattr__(self, "status", ReturnStatus(self.status))
        if self.handed_over_at is not None:
            object.__setattr__(self, "handed_over_at", _utc(self.handed_over_at, "handed_over_at"))
        if (self.handed_over_at is not None) != (self.status == ReturnStatus.HANDED_OVER):
            raise ValueError("El estado de Return y su fecha de salida son incompatibles")
        if self.handed_over_at is not None and self.handed_over_at < self.received_at:
            raise ValueError("La salida no puede ser anterior a la recepción")

    def hand_over(self, at: datetime) -> "Return":
        if self.status != ReturnStatus.AWAITING_CARRIER:
            raise CustodyConflictError("El paquete ya se ha entregado al transportista")
        return replace(self, status=ReturnStatus.HANDED_OVER, handed_over_at=_exit_at(at, self.received_at))

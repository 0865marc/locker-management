from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from domain.lockers import Dimensions, validate_assignment
from domain.validation import CustodyConflictError, _text, _optional_text, _utc, _uuid, _exit_at


class ReturnStatus(str, Enum):
    AWAITING_CARRIER = "AWAITING_CARRIER"
    HANDED_OVER = "HANDED_OVER"


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
        object.__setattr__(self, "tracking_number", _text(self.tracking_number, "tracking_number"))
        object.__setattr__(self, "carrier_code", _text(self.carrier_code, "carrier_code"))
        object.__setattr__(self, "received_at", _utc(self.received_at, "received_at"))
        object.__setattr__(self, "id", _uuid(self.id))
        validate_assignment(self.locker_id, self.compartment_id, self.parcel_dimensions)
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

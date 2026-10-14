from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass(frozen=True)
class Delivery:
    address: str
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        address = self.address.strip()
        if not address:
            raise ValueError("La dirección no puede estar vacía")
        object.__setattr__(self, "address", address)


@dataclass(frozen=True)
class Return:
    reason: str
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        reason = self.reason.strip()
        if not reason:
            raise ValueError("El motivo no puede estar vacío")
        object.__setattr__(self, "reason", reason)

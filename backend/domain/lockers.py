"""Physical capacity values, independent of transport and persistence."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


class LockerNotFoundError(LookupError):
    pass


class CapacityConflictError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class AvailabilityReason(str, Enum):
    NO_LOCKER = 'NO_LOCKER'
    LOCKER_INACTIVE = 'LOCKER_INACTIVE'
    NO_COMPATIBLE_CELL = 'NO_COMPATIBLE_CELL'
    FULL = 'FULL'
    AVAILABLE = 'AVAILABLE'


@dataclass(frozen=True)
class Dimensions:
    width_mm: int
    height_mm: int
    depth_mm: int

    def __post_init__(self):
        if any(type(value) is not int or not 1 <= value <= 2147483647
               for value in (self.width_mm, self.height_mm, self.depth_mm)):
            raise ValueError('Las dimensiones deben ser enteros entre 1 y 2147483647')

    @property
    def volume(self) -> int:
        return self.width_mm * self.height_mm * self.depth_mm

    def fits_in(self, other: 'Dimensions') -> bool:
        return all(a <= b for a, b in zip(sorted(self.axes), sorted(other.axes)))

    @property
    def axes(self):
        return self.width_mm, self.height_mm, self.depth_mm


@dataclass(frozen=True)
class CompartmentBatch:
    quantity: int
    dimensions: Dimensions
    enabled: bool = True

    def __post_init__(self):
        if type(self.quantity) is not int or self.quantity < 1:
            raise ValueError('quantity debe ser un entero positivo')
        if not isinstance(self.dimensions, Dimensions) or type(self.enabled) is not bool:
            raise ValueError('Lote inválido')


def validate_batches(batches):
    if not batches or any(not isinstance(batch, CompartmentBatch) for batch in batches):
        raise ValueError('compartments debe contener lotes')
    if sum(batch.quantity for batch in batches) > 1000:
        raise ValueError('Máximo 1000 celdas nuevas por petición')


@dataclass(frozen=True)
class Compartment:
    locker_id: UUID
    dimensions: Dimensions
    enabled: bool = True
    retired: bool = False
    occupied: bool = False
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        if not isinstance(self.id, UUID) or not isinstance(self.locker_id, UUID):
            raise ValueError('Identificador inválido')
        if not isinstance(self.dimensions, Dimensions) or any(type(v) is not bool for v in (self.enabled, self.retired, self.occupied)):
            raise ValueError('Celda inválida')
        if self.retired and self.enabled:
            raise ValueError('Una celda retirada no puede estar habilitada')


def select_compartment(cells, dimensions):
    candidates = [cell for cell in cells if cell.enabled and not cell.retired and not cell.occupied and dimensions.fits_in(cell.dimensions)]
    return min(candidates, key=lambda cell: (cell.dimensions.volume, cell.id)) if candidates else None


@dataclass(frozen=True)
class Locker:
    location_id: str
    active: bool = True
    compartments: tuple[Compartment, ...] = ()
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        if not isinstance(self.location_id, str) or not self.location_id.strip():
            raise ValueError('location_id debe ser texto no vacío')
        object.__setattr__(self, 'location_id', self.location_id.strip())
        if type(self.active) is not bool or not isinstance(self.id, UUID):
            raise ValueError('Locker inválido')
        if any(cell.locker_id != self.id for cell in self.compartments):
            raise ValueError('Celda ajena al locker')

    @property
    def compartment_count(self):
        return len([cell for cell in self.compartments if not cell.retired])


@dataclass(frozen=True)
class LockerAvailability:
    locker_id: UUID
    active: bool
    compatible_count: int
    available_count: int
    reason: AvailabilityReason


@dataclass(frozen=True)
class Availability:
    location_id: str
    parcel_dimensions: Dimensions
    checked_at: datetime
    reason: AvailabilityReason
    lockers: tuple[LockerAvailability, ...]

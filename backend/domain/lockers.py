"""Physical capacity values, independent of transport and persistence."""
from collections.abc import Iterable, Sequence
from math import isfinite
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4
from typing import TypeVar


ValueT = TypeVar('ValueT')


def require_instance(value: object, expected: type[ValueT], message: str) -> ValueT:
    """Validate an untrusted Python boundary and return its narrowed value."""
    if not isinstance(value, expected):
        raise ValueError(message)
    return value


class LockerNotFoundError(LookupError):
    pass


class CapacityConflictError(ValueError):
    def __init__(self, code: str) -> None:
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

    def __post_init__(self) -> None:
        if any(type(value) is not int or not 1 <= value <= 2147483647
               for value in (self.width_mm, self.height_mm, self.depth_mm)):
            raise ValueError('Las dimensiones deben ser enteros entre 1 y 2147483647')

    @property
    def volume(self) -> int:
        return self.width_mm * self.height_mm * self.depth_mm

    def fits_in(self, other: 'Dimensions') -> bool:
        return all(a <= b for a, b in zip(sorted(self.axes), sorted(other.axes)))

    @property
    def axes(self) -> tuple[int, int, int]:
        return self.width_mm, self.height_mm, self.depth_mm


@dataclass(frozen=True)
class CompartmentBatch:
    quantity: int
    dimensions: Dimensions
    enabled: bool = True

    def __post_init__(self) -> None:
        if type(self.quantity) is not int or self.quantity < 1:
            raise ValueError('quantity debe ser un entero positivo')
        require_instance(self.dimensions, Dimensions, 'Lote inválido')
        if type(self.enabled) is not bool:
            raise ValueError('Lote inválido')


def validate_batches(batches: Sequence[CompartmentBatch]) -> None:
    if not batches:
        raise ValueError('compartments debe contener lotes')
    validated = [require_instance(batch, CompartmentBatch, 'compartments debe contener lotes') for batch in batches]
    if sum(batch.quantity for batch in validated) > 1000:
        raise ValueError('Máximo 1000 celdas nuevas por petición')


@dataclass(frozen=True)
class Compartment:
    locker_id: UUID
    dimensions: Dimensions
    enabled: bool = True
    retired: bool = False
    occupied: bool = False
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        require_instance(self.id, UUID, 'Identificador inválido')
        require_instance(self.locker_id, UUID, 'Identificador inválido')
        require_instance(self.dimensions, Dimensions, 'Celda inválida')
        if any(type(v) is not bool for v in (self.enabled, self.retired, self.occupied)):
            raise ValueError('Celda inválida')
        if self.retired and self.enabled:
            raise ValueError('Una celda retirada no puede estar habilitada')


def select_compartment(cells: Iterable[Compartment], dimensions: Dimensions) -> Compartment | None:
    candidates = [cell for cell in cells if cell.enabled and not cell.retired and not cell.occupied and dimensions.fits_in(cell.dimensions)]
    return min(candidates, key=lambda cell: (cell.dimensions.volume, cell.id)) if candidates else None


def location_alias(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError('location_id debe ser texto no vacío')
    return value.strip()


@dataclass(frozen=True)
class Address:
    country_code: str
    postal_code: str
    province: str
    city: str
    street: str
    street_number: str

    def __post_init__(self) -> None:
        if self.country_code != 'ES':
            raise ValueError('country_code debe ser ES')
        postal_code = require_instance(self.postal_code, str, 'postal_code debe tener cinco dígitos ASCII')
        if re.fullmatch(r'[0-9]{5}', postal_code) is None:
            raise ValueError('postal_code debe tener cinco dígitos ASCII')
        for name in ('province', 'city', 'street', 'street_number'):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'{name} debe ser texto no vacío')
            object.__setattr__(self, name, value.strip())


@dataclass(frozen=True)
class Coordinates:
    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        for name, limit in (('latitude', 90), ('longitude', 180)):
            value = getattr(self, name)
            if type(value) not in (int, float) or not isinstance(value, (int, float)) or not -limit <= value <= limit or not isfinite(value):
                raise ValueError(f'{name} debe ser un número finito entre {-limit} y {limit}')
            object.__setattr__(self, name, float(value))


@dataclass(frozen=True)
class LockerPatch:
    active: bool | None = None
    address: Address | None = None
    coordinates: Coordinates | None = None
    address_supplied: bool = False
    coordinates_supplied: bool = False

    def __post_init__(self) -> None:
        if self.active is not None and type(self.active) is not bool:
            raise ValueError('active debe ser booleano')
        if self.active is None and not self.address_supplied and not self.coordinates_supplied:
            raise ValueError('Indique active, address o coordinates')
        if self.address is not None:
            require_instance(self.address, Address, 'address inválido')
            if not self.address_supplied:
                raise ValueError('address inválido')
        if self.coordinates is not None:
            require_instance(self.coordinates, Coordinates, 'coordinates inválidas')
            if not self.coordinates_supplied:
                raise ValueError('coordinates inválidas')


@dataclass(frozen=True)
class Locker:
    location_id: str | None = None
    active: bool = True
    compartments: tuple[Compartment, ...] = ()
    id: UUID = field(default_factory=uuid4)

    address: Address | None = None
    coordinates: Coordinates | None = None

    def __post_init__(self) -> None:
        if self.location_id is not None:
            object.__setattr__(self, 'location_id', location_alias(self.location_id))
        if self.address is not None:
            require_instance(self.address, Address, 'address inválido')
        if self.coordinates is not None:
            require_instance(self.coordinates, Coordinates, 'coordinates inválidas')
        require_instance(self.id, UUID, 'Locker inválido')
        if type(self.active) is not bool:
            raise ValueError('Locker inválido')
        if any(cell.locker_id != self.id for cell in self.compartments):
            raise ValueError('Celda ajena al locker')

    @property
    def compartment_count(self) -> int:
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

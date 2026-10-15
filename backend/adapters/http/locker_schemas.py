from uuid import UUID
from typing import Self
from math import isfinite
from datetime import datetime
from pydantic import BaseModel, ConfigDict, StrictBool, StrictInt, StrictStr, Field, model_validator, field_validator
from domain.lockers import Dimensions, CompartmentBatch, AvailabilityReason, Address, Coordinates, LockerPatch

class DimensionsInput(BaseModel):
    model_config = ConfigDict(extra='forbid', from_attributes=True)
    width_mm: StrictInt = Field(ge=1, le=2147483647)
    height_mm: StrictInt = Field(ge=1, le=2147483647)
    depth_mm: StrictInt = Field(ge=1, le=2147483647)
    def domain(self) -> Dimensions:
        return Dimensions(self.width_mm, self.height_mm, self.depth_mm)

class BatchInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    quantity: StrictInt = Field(ge=1)
    dimensions: DimensionsInput
    enabled: StrictBool = True
    def domain(self) -> CompartmentBatch:
        return CompartmentBatch(self.quantity, self.dimensions.domain(), self.enabled)

class AddCompartments(BaseModel):
    model_config = ConfigDict(extra='forbid')
    compartments: list[BatchInput] = Field(min_length=1)
    @model_validator(mode='after')
    def bounded(self) -> Self:
        if sum(b.quantity for b in self.compartments) > 1000:
            raise ValueError('Máximo 1000 celdas nuevas por petición')
        return self

class AddressInput(BaseModel):
    model_config = ConfigDict(extra='forbid', from_attributes=True)
    country_code: StrictStr
    postal_code: StrictStr
    province: StrictStr
    city: StrictStr
    street: StrictStr
    street_number: StrictStr

    def domain(self) -> Address:
        return Address(self.country_code, self.postal_code, self.province, self.city, self.street, self.street_number)

    @model_validator(mode='after')
    def valid(self) -> Self:
        self.domain()
        return self


class CoordinatesInput(BaseModel):
    model_config = ConfigDict(extra='forbid', from_attributes=True)
    latitude: float
    longitude: float

    @field_validator('latitude', 'longitude', mode='before')
    @classmethod
    def number(cls, value: object) -> float:
        if type(value) not in (int, float) or not isinstance(value, (int, float)) or not -180 <= value <= 180 or not isfinite(value):
            raise ValueError('Las coordenadas deben ser números JSON finitos')
        return float(value)

    def domain(self) -> Coordinates:
        return Coordinates(self.latitude, self.longitude)

    @model_validator(mode='after')
    def valid(self) -> Self:
        self.domain()
        return self


class CreateLocker(AddCompartments):
    location_id: StrictStr | None = None
    active: StrictBool = True
    address: AddressInput | None = None
    coordinates: CoordinatesInput | None = None

    @model_validator(mode='after')
    def locator(self) -> Self:
        if self.location_id is None and self.address is None:
            raise ValueError('Se requiere location_id o address')
        return self


class UpdateLocker(BaseModel):
    model_config = ConfigDict(extra='forbid')
    active: StrictBool | None = None
    address: AddressInput | None = None
    coordinates: CoordinatesInput | None = None

    @model_validator(mode='after')
    def nonempty(self) -> Self:
        if not self.model_fields_set or ('active' in self.model_fields_set and self.active is None):
            raise ValueError('Indique active no nulo y/o geografía')
        return self

    def domain(self) -> LockerPatch:
        return LockerPatch(active=self.active,
            address=self.address.domain() if self.address is not None else None,
            coordinates=self.coordinates.domain() if self.coordinates is not None else None,
            address_supplied='address' in self.model_fields_set,
            coordinates_supplied='coordinates' in self.model_fields_set)

class UpdateCompartment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    dimensions: DimensionsInput | None = None
    enabled: StrictBool | None = None
    @model_validator(mode='after')
    def nonempty(self) -> Self:
        if not self.model_fields_set or any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError('Indique dimensions y/o enabled no nulos')
        return self

class CompartmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    dimensions: DimensionsInput
    enabled: bool
    occupied: bool

class LockerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    location_id: str | None
    address: AddressInput | None
    coordinates: CoordinatesInput | None
    active: bool
    compartment_count: int
    compartments: list[CompartmentResponse]

class LockerAvailabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    locker_id: UUID
    active: bool
    compatible_count: int
    available_count: int
    reason: AvailabilityReason

class AvailabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    location_id: str
    parcel_dimensions: DimensionsInput
    checked_at: datetime
    reason: AvailabilityReason
    lockers: list[LockerAvailabilityResponse]

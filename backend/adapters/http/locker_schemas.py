from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, StrictBool, StrictInt, StrictStr, Field, model_validator
from domain.lockers import Dimensions, CompartmentBatch, AvailabilityReason

class DimensionsInput(BaseModel):
    model_config = ConfigDict(extra='forbid', from_attributes=True)
    width_mm: StrictInt = Field(ge=1, le=2147483647)
    height_mm: StrictInt = Field(ge=1, le=2147483647)
    depth_mm: StrictInt = Field(ge=1, le=2147483647)
    def domain(self):
        return Dimensions(**self.model_dump())

class BatchInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    quantity: StrictInt = Field(ge=1)
    dimensions: DimensionsInput
    enabled: StrictBool = True
    def domain(self):
        return CompartmentBatch(self.quantity, self.dimensions.domain(), self.enabled)

class AddCompartments(BaseModel):
    model_config = ConfigDict(extra='forbid')
    compartments: list[BatchInput] = Field(min_length=1)
    @model_validator(mode='after')
    def bounded(self):
        if sum(b.quantity for b in self.compartments) > 1000:
            raise ValueError('Máximo 1000 celdas nuevas por petición')
        return self

class CreateLocker(AddCompartments):
    location_id: StrictStr
    active: StrictBool = True

class UpdateLocker(BaseModel):
    model_config = ConfigDict(extra='forbid')
    active: StrictBool

class UpdateCompartment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    dimensions: DimensionsInput | None = None
    enabled: StrictBool | None = None
    @model_validator(mode='after')
    def nonempty(self):
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
    location_id: str
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

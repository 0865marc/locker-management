from uuid import UUID

from pydantic import BaseModel


class CreateDelivery(BaseModel):
    address: str


class DeliveryResponse(BaseModel):
    id: UUID
    address: str


class CreateReturn(BaseModel):
    reason: str


class ReturnResponse(BaseModel):
    id: UUID
    reason: str

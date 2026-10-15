"""Immutable transport inputs and normalized provider outcomes, without infrastructure."""
from dataclasses import dataclass

from domain.lockers import Dimensions, require_instance
from typing import TypeGuard


def validate_code(value: object, name: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f'{name} must be nonblank trimmed text')


def _positive_integer(value: object, name: str) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f'{name} must be a positive integer')


def _validate_postal(value: object) -> None:
    if (not isinstance(value, str) or len(value) != 5
            or any(character not in '0123456789' for character in value)):
        raise ValueError('Postal codes must contain five ASCII digits')


@dataclass(frozen=True)
class ShippingQuoteRequest:
    origin_country_code: str
    origin_postal_code: str
    destination_country_code: str
    destination_postal_code: str
    weight_grams: int
    dimensions: Dimensions

    def __post_init__(self) -> None:
        if self.origin_country_code != 'ES' or self.destination_country_code != 'ES':
            raise ValueError('Only country ES is supported')
        _validate_postal(self.origin_postal_code)
        _validate_postal(self.destination_postal_code)
        if type(self.weight_grams) is not int or not 1 <= self.weight_grams <= 30000:
            raise ValueError('weight_grams must be an integer between 1 and 30000')
        dimensions = require_instance(self.dimensions, Dimensions, 'dimensions must be Dimensions')
        if any(type(axis) is not int or not 1 <= axis <= 2000 for axis in dimensions.axes):
            raise ValueError('Shipping dimensions must be integers between 1 and 2000 mm')


@dataclass(frozen=True)
class ShippingOffer:
    service_code: str
    price_cents: int
    currency: str
    transit_days_min: int
    transit_days_max: int

    def __post_init__(self) -> None:
        validate_code(self.service_code, 'service_code')
        _positive_integer(self.price_cents, 'price_cents')
        if self.currency != 'EUR':
            raise ValueError('Only currency EUR is supported')
        _positive_integer(self.transit_days_min, 'transit_days_min')
        _positive_integer(self.transit_days_max, 'transit_days_max')
        if self.transit_days_min > self.transit_days_max:
            raise ValueError('Transit interval must be ordered')


def _is_object_tuple(value: object) -> TypeGuard[tuple[object, ...]]:
    return isinstance(value, tuple)


def _validate_offers(offers: object) -> None:
    if not _is_object_tuple(offers):
        raise ValueError('offers must be an immutable tuple')
    codes: set[str] = set()
    for candidate in offers:
        offer = require_instance(candidate, ShippingOffer, 'Every offer must be ShippingOffer')
        offer.__post_init__()
        if offer.service_code in codes:
            raise ValueError('service_code must be unique within a provider')
        codes.add(offer.service_code)


@dataclass(frozen=True)
class QuoteOffers:
    offers: tuple[ShippingOffer, ...]

    def __post_init__(self) -> None:
        _validate_offers(self.offers)
        if not self.offers:
            raise ValueError('QuoteOffers must contain at least one offer')


@dataclass(frozen=True)
class NoCoverage:
    """A valid business rejection, distinct from a technical failure."""

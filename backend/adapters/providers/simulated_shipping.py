"""Fixed provider behavior with cancellable simulation and unchanged tariffs."""
import asyncio
from dataclasses import dataclass
import random
from typing import ClassVar

from application.quotations.errors import ProviderTechnicalError
from domain.shipping_quotes import QuoteOffers, ShippingOffer, ShippingQuoteRequest

# Private execution-time lookups keep production construction free of test settings.
_random = random.random
_uniform = random.uniform
_sleep = asyncio.sleep


@dataclass(frozen=True)
class _SimulationProfile:
    delay_min_seconds: float
    delay_max_seconds: float
    no_response_probability: float
    error_probability: float


async def _simulate(profile: _SimulationProfile) -> None:
    outcome = _random()
    delay = _uniform(profile.delay_min_seconds, profile.delay_max_seconds)
    await _sleep(delay)
    if outcome < profile.no_response_probability:
        await asyncio.Event().wait()
    elif outcome < profile.no_response_probability + profile.error_probability:
        raise ProviderTechnicalError('Simulated provider failure')


def _billable_weight_and_zone(request: ShippingQuoteRequest) -> tuple[int, int]:
    volume_grams = (request.dimensions.volume + 4999) // 5000
    kilograms = (max(request.weight_grams, volume_grams) + 999) // 1000
    zone = int(request.origin_postal_code[:2] != request.destination_postal_code[:2])
    return kilograms, zone


class SimulatedEconomyProvider:
    __profile: ClassVar[_SimulationProfile] = _SimulationProfile(0.2, 0.8, 0.10, 0.15)

    @property
    def code(self) -> str:
        return 'sim-economy'

    async def quote(self, request: ShippingQuoteRequest) -> QuoteOffers:
        await _simulate(self.__profile)
        kilograms, zone = _billable_weight_and_zone(request)
        days = 3 + zone
        return QuoteOffers((ShippingOffer('economy', 250 + 40 * kilograms + 100 * zone,
                                         'EUR', days, days),))


class SimulatedStandardProvider:
    __profile: ClassVar[_SimulationProfile] = _SimulationProfile(0.1, 0.5, 0.05, 0.10)

    @property
    def code(self) -> str:
        return 'sim-standard'

    async def quote(self, request: ShippingQuoteRequest) -> QuoteOffers:
        await _simulate(self.__profile)
        kilograms, zone = _billable_weight_and_zone(request)
        days = 2 + zone
        return QuoteOffers((ShippingOffer('standard', 400 + 60 * kilograms + 150 * zone,
                                         'EUR', days, days),))


class SimulatedExpressProvider:
    __profile: ClassVar[_SimulationProfile] = _SimulationProfile(0.05, 0.2, 0.02, 0.05)

    @property
    def code(self) -> str:
        return 'sim-express'

    async def quote(self, request: ShippingQuoteRequest) -> QuoteOffers:
        await _simulate(self.__profile)
        kilograms, zone = _billable_weight_and_zone(request)
        days = 1 + zone
        return QuoteOffers((ShippingOffer('express', 650 + 90 * kilograms + 200 * zone,
                                         'EUR', days, days),))

"""Example tariffs with optional, cancellable transport behavior simulation."""

import asyncio
import math
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from domain.ports import ProviderTechnicalError
from domain.shipping_quotes import QuoteOffers, ShippingOffer, ShippingQuoteRequest


def _validate_finite_number(value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Simulation settings must be finite real numbers")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError("Simulation settings must be finite real numbers")


@dataclass(frozen=True)
class SimulationProfile:
    delay_min_seconds: float = 0
    delay_max_seconds: float = 0
    no_response_probability: float = 0
    error_probability: float = 0

    def __post_init__(self) -> None:
        values = (
            self.delay_min_seconds,
            self.delay_max_seconds,
            self.no_response_probability,
            self.error_probability,
        )
        for value in values:
            _validate_finite_number(value)
        if not 0 <= self.delay_min_seconds <= self.delay_max_seconds:
            raise ValueError("Simulation delays require 0 <= min <= max")
        if not (
            0 <= self.no_response_probability <= 1
            and 0 <= self.error_probability <= 1
            and self.no_response_probability + self.error_probability <= 1
        ):
            raise ValueError(
                "Simulation probabilities require values in [0, 1] and sum <= 1"
            )


class SimulationRandom(Protocol):
    def random(self) -> float: ...

    def uniform(self, a: float, b: float) -> float: ...


class _SimulatedProvider:
    def __init__(
        self,
        profile: SimulationProfile | None = None,
        *,
        rng: SimulationRandom | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._profile = profile if profile is not None else SimulationProfile()
        self._rng = rng if rng is not None else random.Random()
        self._sleep = sleep

    async def _simulate(self) -> None:
        profile = self._profile
        # Direct construction avoids both random draws and even a zero-second yield.
        if profile == SimulationProfile():
            return
        outcome = self._rng.random()
        delay = self._rng.uniform(profile.delay_min_seconds, profile.delay_max_seconds)
        await self._sleep(delay)
        if outcome < profile.no_response_probability:
            await asyncio.Event().wait()
        elif outcome < profile.no_response_probability + profile.error_probability:
            raise ProviderTechnicalError("Simulated provider failure")


def _billable_weight_and_zone(request: ShippingQuoteRequest) -> tuple[int, int]:
    volume_grams = (request.dimensions.volume + 4999) // 5000
    kilograms = (max(request.weight_grams, volume_grams) + 999) // 1000
    zone = int(request.origin_postal_code[:2] != request.destination_postal_code[:2])
    return kilograms, zone


class SimulatedEconomyProvider(_SimulatedProvider):
    @property
    def code(self) -> str:
        return "sim-economy"

    async def quote(self, request: ShippingQuoteRequest) -> QuoteOffers:
        await self._simulate()
        kilograms, zone = _billable_weight_and_zone(request)
        days = 3 + zone
        return QuoteOffers(
            (
                ShippingOffer(
                    "economy", 250 + 40 * kilograms + 100 * zone, "EUR", days, days
                ),
            )
        )


class SimulatedStandardProvider(_SimulatedProvider):
    @property
    def code(self) -> str:
        return "sim-standard"

    async def quote(self, request: ShippingQuoteRequest) -> QuoteOffers:
        await self._simulate()
        kilograms, zone = _billable_weight_and_zone(request)
        days = 2 + zone
        return QuoteOffers(
            (
                ShippingOffer(
                    "standard", 400 + 60 * kilograms + 150 * zone, "EUR", days, days
                ),
            )
        )


class SimulatedExpressProvider(_SimulatedProvider):
    @property
    def code(self) -> str:
        return "sim-express"

    async def quote(self, request: ShippingQuoteRequest) -> QuoteOffers:
        await self._simulate()
        kilograms, zone = _billable_weight_and_zone(request)
        days = 1 + zone
        return QuoteOffers(
            (
                ShippingOffer(
                    "express", 650 + 90 * kilograms + 200 * zone, "EUR", days, days
                ),
            )
        )

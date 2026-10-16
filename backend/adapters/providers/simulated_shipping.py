"""Deterministic example tariffs; no network, random values or stored quotes."""
from domain.shipping_quotes import QuoteOffers, ShippingOffer, ShippingQuoteRequest


def _billable_weight_and_zone(request: ShippingQuoteRequest) -> tuple[int, int]:
    volume_grams = (request.dimensions.volume + 4999) // 5000
    kilograms = (max(request.weight_grams, volume_grams) + 999) // 1000
    zone = int(request.origin_postal_code[:2] != request.destination_postal_code[:2])
    return kilograms, zone


class SimulatedEconomyProvider:
    @property
    def code(self) -> str:
        return 'sim-economy'

    async def quote(self, request: ShippingQuoteRequest) -> QuoteOffers:
        kilograms, zone = _billable_weight_and_zone(request)
        days = 3 + zone
        return QuoteOffers((ShippingOffer('economy', 250 + 40 * kilograms + 100 * zone,
                                         'EUR', days, days),))


class SimulatedStandardProvider:
    @property
    def code(self) -> str:
        return 'sim-standard'

    async def quote(self, request: ShippingQuoteRequest) -> QuoteOffers:
        kilograms, zone = _billable_weight_and_zone(request)
        days = 2 + zone
        return QuoteOffers((ShippingOffer('standard', 400 + 60 * kilograms + 150 * zone,
                                         'EUR', days, days),))


class SimulatedExpressProvider:
    @property
    def code(self) -> str:
        return 'sim-express'

    async def quote(self, request: ShippingQuoteRequest) -> QuoteOffers:
        kilograms, zone = _billable_weight_and_zone(request)
        days = 1 + zone
        return QuoteOffers((ShippingOffer('express', 650 + 90 * kilograms + 200 * zone,
                                         'EUR', days, days),))

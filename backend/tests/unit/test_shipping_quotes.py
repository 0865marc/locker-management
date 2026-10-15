"""Direct transport contracts and observable async scheduling, without services."""
import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import FrozenInstanceError, replace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch

from adapters.providers.simulated_shipping import (
    SimulatedEconomyProvider,
    SimulatedExpressProvider,
    SimulatedStandardProvider,
)
from application.shipping_quote_use_cases import QuoteShipping
from domain.lockers import Dimensions
from domain.ports import ProviderTechnicalError, ShippingProvider
from domain.shipping_quotes import (
    NoCoverage,
    ProviderErrorCode,
    ProviderResult,
    ProviderStatus,
    QuoteOffers,
    ShippingOffer,
    ShippingQuoteRequest,
)


def request() -> ShippingQuoteRequest:
    return ShippingQuoteRequest('ES', '01001', 'ES', '01002', 1200, Dimensions(200, 150, 100))


def offers() -> QuoteOffers:
    return QuoteOffers((ShippingOffer('service', 500, 'EUR', 1, 3),))


class ProviderDouble:
    def __init__(
        self, code: str,
        callback: Callable[[ShippingQuoteRequest], Awaitable[QuoteOffers | NoCoverage]] | None = None,
    ) -> None:
        self._code = code
        self.callback = callback
        self.calls = 0

    @property
    def code(self) -> str:
        return self._code

    async def quote(self, request: ShippingQuoteRequest) -> QuoteOffers | NoCoverage:
        self.calls += 1
        return await self.callback(request) if self.callback is not None else offers()


class ShippingContractTests(TestCase):
    def test_request_boundaries_leading_zero_and_dimensions_reuse(self) -> None:
        original = request()
        self.assertEqual(original.origin_postal_code, '01001')
        self.assertIsInstance(original.dimensions, Dimensions)
        for weight in (1, 30000):
            for axes in ((1, 1, 1), (2000, 2000, 2000)):
                value = replace(original, weight_grams=weight, dimensions=Dimensions(*axes))
                self.assertEqual(value.weight_grams, weight)
        self.assertEqual(Dimensions(2147483647, 1, 1).width_mm, 2147483647)
        with self.assertRaises(FrozenInstanceError):
            setattr(original, 'weight_grams', 99)

    def test_request_rejects_malformed_inputs(self) -> None:
        changes: list[dict[str, object]] = [
            {'origin_country_code': 'FR'}, {'destination_country_code': 'es'},
            {'origin_postal_code': ' 01001'}, {'origin_postal_code': '0101'},
            {'origin_postal_code': '٠١٠٠١'}, {'origin_postal_code': '０１００１'},
            {'destination_postal_code': 1001}, {'origin_postal_code': None},
            {'weight_grams': 0}, {'weight_grams': 30001}, {'weight_grams': True},
            {'weight_grams': 1200.0}, {'weight_grams': '1200'},
            {'dimensions': Dimensions(2001, 1, 1)}, {'dimensions': (1, 2, 3)},
        ]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(request(), **change)

    def test_offer_invariants_and_open_case_sensitive_service_codes(self) -> None:
        original = offers().offers[0]
        changes: list[dict[str, object]] = [
            {'service_code': ''}, {'service_code': '  '}, {'service_code': ' code'},
            {'service_code': None}, {'price_cents': 0}, {'price_cents': -1},
            {'price_cents': True}, {'price_cents': 1.5}, {'price_cents': '500'},
            {'currency': 'USD'}, {'transit_days_min': 0}, {'transit_days_max': 0},
            {'transit_days_min': True}, {'transit_days_max': 1.0},
            {'transit_days_min': 4},
        ]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(original, **change)
        upper = replace(original, service_code='Custom-V9')
        lower = replace(original, service_code='custom-v9')
        self.assertEqual(len(QuoteOffers((upper, lower)).offers), 2)
        for invalid in ((), (original, original), [original], ('raw payload',)):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                replace(offers(), offers=invalid)

    def test_provider_result_status_invariants_and_immutability(self) -> None:
        quoted = ProviderResult('New-Provider', ProviderStatus.QUOTED, offers().offers)
        self.assertEqual(quoted.status, 'QUOTED')
        self.assertEqual(ProviderResult('p', ProviderStatus.NOT_COVERED).offers, ())
        for error in ProviderErrorCode:
            self.assertEqual(ProviderResult('p', ProviderStatus.FAILED, error_code=error).error_code, error)
        changes: list[dict[str, object]] = [
            {'provider_code': ''}, {'provider_code': ' p'}, {'offers': ()},
            {'error_code': ProviderErrorCode.PROVIDER_ERROR}, {'status': 'invalid'},
            {'status': ProviderStatus.NOT_COVERED}, {'status': ProviderStatus.FAILED},
        ]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(quoted, **change)
        with self.assertRaises(ValueError):
            ProviderResult('p', ProviderStatus.FAILED, error_code=None)
        with self.assertRaises(ValueError):
            ProviderResult('p', ProviderStatus.NOT_COVERED, error_code=ProviderErrorCode.PROVIDER_ERROR)
        with self.assertRaises(FrozenInstanceError):
            setattr(quoted, 'offers', ())

    def test_configuration_rejected_before_any_calls(self) -> None:
        provider = ProviderDouble('valid')
        collections: list[list[ShippingProvider]] = [[], [provider, provider]]
        collections.extend([[ProviderDouble(code)] for code in ('', ' ', ' untrimmed', 'trailing ')])
        for collection in collections:
            with self.subTest(collection=collection), self.assertRaises(ValueError):
                QuoteShipping(collection)
        bad_settings: list[dict[str, object]] = [
            {'max_concurrency': 0}, {'max_concurrency': True}, {'max_concurrency': 1.0},
            {'timeout_seconds': 0}, {'timeout_seconds': -1}, {'timeout_seconds': True},
            {'timeout_seconds': float('nan')}, {'timeout_seconds': float('inf')},
        ]
        for settings in bad_settings:
            with self.subTest(settings=settings):
                # Deliberate runtime contract checks; unittest invokes the typed constructor.
                self.assertRaises(ValueError, QuoteShipping, [provider], **settings)
        self.assertEqual(provider.calls, 0)


class ShippingComparisonTests(IsolatedAsyncioTestCase):
    async def test_three_simulators_documented_example_and_fourth_with_two_services(self) -> None:
        async def multiple(value: ShippingQuoteRequest) -> QuoteOffers:
            self.assertEqual(value, request())
            return QuoteOffers((ShippingOffer('z-priority', 800, 'EUR', 1, 2),
                                ShippingOffer('a-budget', 300, 'EUR', 4, 6)))

        fourth = ProviderDouble('independent-V4', multiple)
        providers: list[ShippingProvider] = [SimulatedStandardProvider(), SimulatedExpressProvider(),
                                             fourth, SimulatedEconomyProvider()]
        comparator = QuoteShipping(providers)
        providers.clear()  # Configuration was copied, including its code identities.
        results = await comparator.compare(request())
        self.assertIsInstance(results, tuple)
        self.assertEqual([result.provider_code for result in results],
                         ['independent-V4', 'sim-economy', 'sim-express', 'sim-standard'])
        self.assertEqual([offer.service_code for offer in results[0].offers], ['a-budget', 'z-priority'])
        self.assertEqual([(result.offers[0].price_cents, result.offers[0].transit_days_min,
                           result.offers[0].transit_days_max) for result in results[1:]],
                         [(330, 3, 3), (830, 1, 1), (520, 2, 2)])
        self.assertEqual(fourth.calls, 1)
        self.assertTrue(all(result.status is ProviderStatus.QUOTED for result in results))

    async def test_simulator_extremes_rounding_zone_and_repeatability(self) -> None:
        comparator = QuoteShipping([SimulatedEconomyProvider(), SimulatedStandardProvider(),
                                    SimulatedExpressProvider()])
        extreme = replace(request(), destination_postal_code='28001', weight_grams=30000,
                          dimensions=Dimensions(2000, 2000, 2000))
        first = await comparator.compare(extreme)
        self.assertEqual(await comparator.compare(extreme), first)
        self.assertEqual([result.offers[0].price_cents for result in first], [64350, 144850, 96550])
        self.assertEqual([result.offers[0].transit_days_min for result in first], [4, 2, 3])
        for weight, dimensions, expected in (
            (1, Dimensions(1, 1, 1), 290),
            (1000, Dimensions(1, 1, 1), 290),
            (1001, Dimensions(1, 1, 1), 330),
            (1, Dimensions(200, 100, 250), 290),
            (1, Dimensions(200, 100, 251), 330),
        ):
            with self.subTest(weight=weight, dimensions=dimensions):
                value = replace(request(), weight_grams=weight, dimensions=dimensions)
                self.assertEqual((await comparator.compare(value))[0].offers[0].price_cents, expected)

    async def test_partial_failures_no_coverage_and_invalid_response_are_distinct(self) -> None:
        async def no_coverage(value: ShippingQuoteRequest) -> NoCoverage:
            return NoCoverage()

        async def technical(value: ShippingQuoteRequest) -> QuoteOffers:
            raise ProviderTechnicalError('sensitive transport details')

        async def unexpected(value: ShippingQuoteRequest) -> QuoteOffers:
            raise RuntimeError('secret external payload')

        async def external_timeout(value: ShippingQuoteRequest) -> QuoteOffers:
            raise TimeoutError('adapter timeout is an ordinary technical error')

        async def malformed(value: ShippingQuoteRequest) -> QuoteOffers:
            invalid = object.__new__(QuoteOffers)
            object.__setattr__(invalid, 'offers', ())
            return invalid

        providers = [ProviderDouble('covered'), ProviderDouble('not-covered', no_coverage),
                     ProviderDouble('technical', technical), ProviderDouble('unexpected', unexpected),
                     ProviderDouble('malformed', malformed), ProviderDouble('external-timeout', external_timeout)]
        results = {item.provider_code: item for item in await QuoteShipping(providers).compare(request())}
        self.assertEqual(results['covered'].status, ProviderStatus.QUOTED)
        self.assertEqual(results['not-covered'], ProviderResult('not-covered', ProviderStatus.NOT_COVERED))
        for code in ('technical', 'unexpected', 'malformed', 'external-timeout'):
            self.assertEqual(results[code], ProviderResult(code, ProviderStatus.FAILED,
                                                          error_code=ProviderErrorCode.PROVIDER_ERROR))
        self.assertTrue(all(provider.calls == 1 for provider in providers))
        self.assertNotIn('secret', repr(results))
        self.assertNotIn('sensitive', repr(results))
        all_rejected = await QuoteShipping(providers[1:]).compare(request())
        self.assertEqual(len(all_rejected), 5)
        self.assertTrue(all(not result.offers for result in all_rejected))

    async def test_malformed_adapter_offer_collections_fail_only_that_provider(self) -> None:
        bad_offer = object.__new__(ShippingOffer)
        for name in ('service_code', 'price_cents', 'currency', 'transit_days_min', 'transit_days_max'):
            object.__setattr__(bad_offer, name, getattr(offers().offers[0], name))
        object.__setattr__(bad_offer, 'price_cents', True)
        invalid_collections: tuple[object, ...] = (
            [offers().offers[0]], (offers().offers[0], offers().offers[0]),
            ('external payload',), (bad_offer,),
        )
        for collection in invalid_collections:
            with self.subTest(collection=collection):
                async def malformed(value: ShippingQuoteRequest) -> QuoteOffers:
                    invalid = object.__new__(QuoteOffers)
                    object.__setattr__(invalid, 'offers', collection)
                    return invalid

                results = await QuoteShipping([ProviderDouble('bad', malformed),
                                               ProviderDouble('good')]).compare(request())
                self.assertEqual(results[0].error_code, ProviderErrorCode.PROVIDER_ERROR)
                self.assertEqual(results[0].offers, ())
                self.assertEqual(results[1].status, ProviderStatus.QUOTED)

    async def test_invalid_request_fails_before_provider_calls(self) -> None:
        provider = ProviderDouble('p')
        invalid = object.__new__(ShippingQuoteRequest)
        for name in ('origin_country_code', 'origin_postal_code', 'destination_country_code',
                     'destination_postal_code', 'weight_grams', 'dimensions'):
            object.__setattr__(invalid, name, getattr(request(), name))
        object.__setattr__(invalid, 'weight_grams', True)
        with self.assertRaises(ValueError):
            await QuoteShipping([provider]).compare(invalid)
        self.assertEqual(provider.calls, 0)

    async def test_default_three_slots_and_waiters_start_only_after_release(self) -> None:
        entered = {code: asyncio.Event() for code in 'abcde'}
        release = {code: asyncio.Event() for code in 'abcde'}
        active = 0
        peak = 0

        def callback(code: str) -> Callable[[ShippingQuoteRequest], Awaitable[QuoteOffers]]:
            async def quote(value: ShippingQuoteRequest) -> QuoteOffers:
                nonlocal active, peak
                active += 1
                peak = max(peak, active)
                entered[code].set()
                try:
                    await release[code].wait()
                    return offers()
                finally:
                    active -= 1
            return quote

        providers = [ProviderDouble(code, callback(code)) for code in 'edcba']
        task = asyncio.create_task(QuoteShipping(providers).compare(request()))
        try:
            await asyncio.wait_for(asyncio.gather(*(entered[code].wait() for code in 'abc')), 1)
            self.assertFalse(entered['d'].is_set())
            self.assertFalse(entered['e'].is_set())
            release['a'].set()
            await asyncio.wait_for(entered['d'].wait(), 1)
            self.assertFalse(entered['e'].is_set())
            release['b'].set()
            await asyncio.wait_for(entered['e'].wait(), 1)
            for gate in release.values():
                gate.set()
            results = await asyncio.wait_for(task, 1)
            self.assertEqual(len(results), 5)
            self.assertEqual(peak, 3)
            self.assertEqual(active, 0)
            self.assertTrue(all(provider.calls == 1 for provider in providers))
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_concurrency_limit_is_per_comparison(self) -> None:
        entered_six = asyncio.Event()
        release = asyncio.Event()
        active = 0

        async def quote(value: ShippingQuoteRequest) -> QuoteOffers:
            nonlocal active
            active += 1
            if active == 6:
                entered_six.set()
            try:
                await release.wait()
                return offers()
            finally:
                active -= 1

        comparator = QuoteShipping([ProviderDouble(code, quote) for code in 'abc'])
        tasks = [asyncio.create_task(comparator.compare(request())) for _ in range(2)]
        try:
            await asyncio.wait_for(entered_six.wait(), 1)
            self.assertEqual(active, 6)
            release.set()
            self.assertEqual([len(result) for result in await asyncio.gather(*tasks)], [3, 3])
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def test_default_two_second_timeout_preserves_other_offers_without_retry(self) -> None:
        entered = asyncio.Event()
        cleaned = asyncio.Event()
        never = asyncio.Event()

        async def slow(value: ShippingQuoteRequest) -> QuoteOffers:
            entered.set()
            try:
                await never.wait()
                return offers()
            finally:
                cleaned.set()

        provider = ProviderDouble('slow', slow)
        results = await asyncio.wait_for(QuoteShipping([provider, ProviderDouble('fast')]).compare(request()), 4)
        self.assertTrue(entered.is_set())
        self.assertTrue(cleaned.is_set())
        self.assertEqual(results[0].status, ProviderStatus.QUOTED)
        self.assertEqual(results[1], ProviderResult('slow', ProviderStatus.FAILED,
                                                  error_code=ProviderErrorCode.PROVIDER_TIMEOUT))
        self.assertEqual(provider.calls, 1)

    async def test_waiting_for_slot_does_not_start_call_timeout(self) -> None:
        cleanup_started = asyncio.Event()
        release_cleanup = asyncio.Event()
        never = asyncio.Event()
        timers: list[asyncio.Timeout] = []
        timeout_factory = asyncio.timeout

        def recorded_timeout(delay: float) -> asyncio.Timeout:
            timer = timeout_factory(delay)
            timers.append(timer)
            return timer

        async def slow(value: ShippingQuoteRequest) -> QuoteOffers:
            try:
                await never.wait()
                return offers()
            finally:
                # Keep the slot owned through cancellation cleanup; the waiter has no timer.
                cleanup_started.set()
                await release_cleanup.wait()

        waiter = ProviderDouble('b-waiter')
        comparator = QuoteShipping([ProviderDouble('a-slow', slow), waiter],
                                   max_concurrency=1, timeout_seconds=0.02)
        with patch('application.shipping_quote_use_cases.asyncio.timeout', recorded_timeout):
            task = asyncio.create_task(comparator.compare(request()))
            try:
                await asyncio.wait_for(cleanup_started.wait(), 1)
                self.assertEqual(len(timers), 1)
                self.assertEqual(waiter.calls, 0)
                self.assertTrue(timers[0].expired())
                release_cleanup.set()
                results = await asyncio.wait_for(task, 1)
                self.assertEqual(len(timers), 2)
                self.assertEqual(results[0].error_code, ProviderErrorCode.PROVIDER_TIMEOUT)
                self.assertEqual(results[1].status, ProviderStatus.QUOTED)
                self.assertEqual(waiter.calls, 1)
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    async def test_caller_cancellation_awaits_active_and_waiting_children(self) -> None:
        all_active = asyncio.Event()
        never = asyncio.Event()
        active = 0
        started = 0
        cleaned = 0

        async def blocked(value: ShippingQuoteRequest) -> QuoteOffers:
            nonlocal active, started, cleaned
            active += 1
            started += 1
            if active == 3:
                all_active.set()
            try:
                await never.wait()
                return offers()
            finally:
                active -= 1
                cleaned += 1

        providers = [ProviderDouble(code, blocked) for code in 'abcdef']
        existing = asyncio.all_tasks()
        task = asyncio.create_task(QuoteShipping(providers).compare(request()))
        await asyncio.wait_for(all_active.wait(), 1)
        owned = asyncio.all_tasks() - existing
        self.assertEqual(len(owned), 7)  # Comparison plus three active and three waiting children.
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual((active, started, cleaned), (0, 3, 3))
        self.assertTrue(all(child.done() for child in owned))
        self.assertEqual(sum(provider.calls for provider in providers), 3)

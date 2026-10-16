import asyncio
from dataclasses import FrozenInstanceError, replace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock

from adapters.providers.simulated_shipping import (
    SimulatedEconomyProvider,
    SimulatedExpressProvider,
    SimulatedStandardProvider,
    SimulationProfile,
)
from application.shipping_quotes import (
    ProviderErrorCode,
    ProviderStatus,
    ShippingQuoteService,
)
from domain.lockers import Dimensions
from domain.ports import ProviderTechnicalError
from domain.shipping_quotes import ShippingQuoteRequest


def request() -> ShippingQuoteRequest:
    return ShippingQuoteRequest(
        "ES", "01001", "ES", "01002", 1200, Dimensions(200, 150, 100)
    )


class ControlledRandom:
    def __init__(self, outcome: float, *, upper_delay: bool = False) -> None:
        self.outcome = outcome
        self.upper_delay = upper_delay
        self.draws = 0
        self.bounds: list[tuple[float, float]] = []

    def random(self) -> float:
        self.draws += 1
        return self.outcome

    def uniform(self, a: float, b: float) -> float:
        self.bounds.append((a, b))
        return b if self.upper_delay else a


class SimulationProfileTests(TestCase):
    def test_invalid_numeric_values_rejected_for_every_setting(self) -> None:
        for field in (
            "delay_min_seconds",
            "delay_max_seconds",
            "no_response_probability",
            "error_probability",
        ):
            for value in (
                True,
                False,
                None,
                "0.1",
                complex(1),
                float("nan"),
                float("inf"),
                -float("inf"),
                10**400,
            ):
                with self.subTest(field=field, value=value):
                    self.assertRaises(ValueError, SimulationProfile, **{field: value})

    def test_bounds_probability_sum_and_immutability(self) -> None:
        for changes in (
            {"delay_min_seconds": -0.1},
            {"delay_max_seconds": -1},
            {"delay_min_seconds": 2, "delay_max_seconds": 1},
            {"no_response_probability": -0.1},
            {"no_response_probability": 1.1},
            {"error_probability": -0.1},
            {"error_probability": 1.1},
            {"no_response_probability": 0.6, "error_probability": 0.5},
        ):
            with self.subTest(changes=changes):
                self.assertRaises(ValueError, SimulationProfile, **changes)
        profile = SimulationProfile(1, 1, 0.25, 0.75)
        self.assertEqual(profile.delay_min_seconds, 1)
        with self.assertRaises(FrozenInstanceError):
            setattr(profile, "error_probability", 0)


class ShippingSimulationTests(IsolatedAsyncioTestCase):
    async def test_default_profile_never_draws_or_sleeps_and_preserves_prices(
        self,
    ) -> None:
        rng = ControlledRandom(0)
        sleep = AsyncMock()
        for provider_type, expected in (
            (SimulatedEconomyProvider, (330, 3)),
            (SimulatedStandardProvider, (520, 2)),
            (SimulatedExpressProvider, (830, 1)),
        ):
            for profile in (None, SimulationProfile()):
                provider = provider_type(profile, rng=rng, sleep=sleep)
                first = await provider.quote(request())
                self.assertEqual(await provider.quote(request()), first)
                self.assertEqual(
                    (first.offers[0].price_cents, first.offers[0].transit_days_min),
                    expected,
                )
        self.assertEqual(rng.draws, 0)
        self.assertEqual(rng.bounds, [])
        sleep.assert_not_awaited()

    async def test_selected_delay_bounds_and_success_preserve_tariffs_at_extremes(
        self,
    ) -> None:
        profile = SimulationProfile(0.05, 0.5, 0.1, 0.2)
        for upper in (False, True):
            for provider_type in (
                SimulatedEconomyProvider,
                SimulatedStandardProvider,
                SimulatedExpressProvider,
            ):
                rng = ControlledRandom(0.9, upper_delay=upper)
                sleep = AsyncMock()
                provider = provider_type(profile, rng=rng, sleep=sleep)
                extreme = replace(
                    request(),
                    destination_postal_code="28001",
                    weight_grams=30000,
                    dimensions=Dimensions(2000, 2000, 2000),
                )
                self.assertEqual(
                    await provider.quote(extreme), await provider_type().quote(extreme)
                )
                sleep.assert_awaited_once_with(0.5 if upper else 0.05)
                self.assertEqual(rng.draws, 1)
                self.assertEqual(rng.bounds, [(0.05, 0.5)])

    async def test_error_is_raised_only_after_selected_delay(self) -> None:
        entered = asyncio.Event()
        release = asyncio.Event()

        async def sleep(delay: float) -> None:
            self.assertEqual(delay, 0.25)
            entered.set()
            await release.wait()

        provider = SimulatedStandardProvider(
            SimulationProfile(0.25, 0.25, 0, 1), rng=ControlledRandom(0), sleep=sleep
        )
        task = asyncio.create_task(provider.quote(request()))
        try:
            await asyncio.wait_for(entered.wait(), 1)
            self.assertFalse(task.done())
            release.set()
            with self.assertRaises(ProviderTechnicalError):
                await task
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_probability_thresholds_select_exclusive_outcomes(self) -> None:
        profile = SimulationProfile(0, 0, 0.25, 0.25)
        for outcome in (0.25, 0.499):
            rng = ControlledRandom(outcome)
            provider = SimulatedEconomyProvider(profile, rng=rng, sleep=AsyncMock())
            with self.assertRaises(ProviderTechnicalError):
                await provider.quote(request())
            self.assertEqual(rng.draws, 1)
        provider = SimulatedEconomyProvider(
            profile, rng=ControlledRandom(0.5), sleep=AsyncMock()
        )
        self.assertEqual(
            await provider.quote(request()),
            await SimulatedEconomyProvider().quote(request()),
        )

    async def test_no_response_wait_is_cancelled_without_detached_tasks(self) -> None:
        delayed = asyncio.Event()

        async def sleep(delay: float) -> None:
            delayed.set()

        rng = ControlledRandom(0.249)
        provider = SimulatedExpressProvider(
            SimulationProfile(0, 0, 0.25, 0.25), rng=rng, sleep=sleep
        )
        existing = asyncio.all_tasks()
        task = asyncio.create_task(provider.quote(request()))
        try:
            await asyncio.wait_for(delayed.wait(), 1)
            self.assertFalse(task.done())
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertEqual(asyncio.all_tasks(), existing)
            self.assertEqual(rng.draws, 1)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_comparison_retains_success_error_timeout_without_retry(self) -> None:
        randoms = [ControlledRandom(0), ControlledRandom(0), ControlledRandom(0)]
        sleeps = [AsyncMock(), AsyncMock(), AsyncMock()]
        success = SimulatedEconomyProvider(
            SimulationProfile(0.01, 0.02), rng=randoms[0], sleep=sleeps[0]
        )
        error = SimulatedStandardProvider(
            SimulationProfile(error_probability=1), rng=randoms[1], sleep=sleeps[1]
        )
        silent = SimulatedExpressProvider(
            SimulationProfile(no_response_probability=1),
            rng=randoms[2],
            sleep=sleeps[2],
        )
        results = await asyncio.wait_for(
            ShippingQuoteService(
                [silent, success, error], timeout_seconds=0.01
            ).compare(request()),
            1,
        )
        by_code = {result.provider_code: result for result in results}
        self.assertEqual(by_code["sim-economy"].status, ProviderStatus.QUOTED)
        self.assertEqual(by_code["sim-economy"].offers[0].price_cents, 330)
        self.assertEqual(
            by_code["sim-standard"].error_code, ProviderErrorCode.PROVIDER_ERROR
        )
        self.assertEqual(
            by_code["sim-express"].error_code, ProviderErrorCode.PROVIDER_TIMEOUT
        )
        self.assertEqual([rng.draws for rng in randoms], [1, 1, 1])
        for sleep in sleeps:
            sleep.assert_awaited_once()

    async def test_cancelling_comparison_cleans_up_an_active_delay(self) -> None:
        entered = asyncio.Event()
        cleaned = asyncio.Event()
        never = asyncio.Event()

        async def sleep(delay: float) -> None:
            entered.set()
            try:
                await never.wait()
            finally:
                cleaned.set()

        rng = ControlledRandom(0.9)
        provider = SimulatedEconomyProvider(
            SimulationProfile(0.1, 0.2), rng=rng, sleep=sleep
        )
        existing = asyncio.all_tasks()
        task = asyncio.create_task(ShippingQuoteService([provider]).compare(request()))
        try:
            await asyncio.wait_for(entered.wait(), 1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertTrue(cleaned.is_set())
            self.assertEqual(asyncio.all_tasks(), existing)
            self.assertEqual(rng.draws, 1)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

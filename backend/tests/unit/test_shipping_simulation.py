"""Fixed production profiles exercised through controlled execution-time functions."""

import asyncio
import inspect
from dataclasses import FrozenInstanceError, replace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch

from adapters.providers import simulated_shipping
from adapters.providers.simulated_shipping import (
    SimulatedEconomyProvider,
    SimulatedExpressProvider,
    SimulatedStandardProvider,
)
from application.quotations.comparison import ShippingQuoteComparator
from application.quotations.errors import ProviderTechnicalError
from application.quotations.models import ProviderErrorCode, ProviderStatus
from domain.lockers import Dimensions
from domain.shipping_quotes import ShippingQuoteRequest

PROVIDERS = (
    (SimulatedEconomyProvider, (0.2, 0.8), 0.10, 0.15, 330, 3, 64350),
    (SimulatedStandardProvider, (0.1, 0.5), 0.05, 0.10, 520, 2, 96550),
    (SimulatedExpressProvider, (0.05, 0.2), 0.02, 0.05, 830, 1, 144850),
)


def request() -> ShippingQuoteRequest:
    return ShippingQuoteRequest(
        "ES", "01001", "ES", "01002", 1200, Dimensions(200, 150, 100)
    )


class FixedProfileTests(TestCase):
    def test_only_zero_argument_construction_and_no_public_configuration_types(self):
        self.assertFalse(hasattr(simulated_shipping, "SimulationProfile"))
        self.assertFalse(hasattr(simulated_shipping, "SimulationRandom"))
        for provider_type, *_ in PROVIDERS:
            self.assertEqual(tuple(inspect.signature(provider_type).parameters), ())
            provider_type()
            self.assertRaises(TypeError, provider_type, object())
            for keyword in ("profile", "rng", "sleep"):
                self.assertRaises(TypeError, provider_type, **{keyword: object()})

    def test_each_provider_owns_a_private_frozen_profile(self):
        for provider_type, bounds, no_response, error, *_ in PROVIDERS:
            profiles = [
                (name, value)
                for name, value in vars(provider_type).items()
                if isinstance(value, simulated_shipping._SimulationProfile)
            ]
            self.assertEqual(len(profiles), 1)
            name, profile = profiles[0]
            self.assertTrue(name.startswith("_" + provider_type.__name__ + "__"))
            self.assertEqual(
                (profile.delay_min_seconds, profile.delay_max_seconds), bounds
            )
            self.assertEqual(
                (profile.no_response_probability, profile.error_probability),
                (no_response, error),
            )
            with self.assertRaises(FrozenInstanceError):
                setattr(profile, "error_probability", 0)


class ShippingSimulationTests(IsolatedAsyncioTestCase):
    async def test_fixed_delay_endpoints_success_tariffs_and_extremes(self):
        extreme = replace(
            request(),
            destination_postal_code="28001",
            weight_grams=30000,
            dimensions=Dimensions(2000, 2000, 2000),
        )
        for provider_type, bounds, _, _, price, days, extreme_price in PROVIDERS:
            provider = (
                provider_type()
            )  # Patch after construction: lookups happen per call.
            for upper in (False, True):
                selected = bounds[int(upper)]
                with (
                    patch.object(
                        simulated_shipping, "_random", return_value=0.99
                    ) as random,
                    patch.object(
                        simulated_shipping, "_uniform", return_value=selected
                    ) as uniform,
                    patch.object(
                        simulated_shipping, "_sleep", new_callable=AsyncMock
                    ) as sleep,
                ):
                    first = await provider.quote(request())
                    self.assertEqual(await provider.quote(request()), first)
                    self.assertEqual(
                        (
                            first.offers[0].price_cents,
                            first.offers[0].transit_days_min,
                            first.offers[0].transit_days_max,
                        ),
                        (price, days, days),
                    )
                    offer = (await provider.quote(extreme)).offers[0]
                    self.assertEqual(
                        (
                            offer.price_cents,
                            offer.transit_days_min,
                            offer.transit_days_max,
                        ),
                        (extreme_price, days + 1, days + 1),
                    )
                    self.assertEqual(random.call_count, 3)
                    self.assertEqual(uniform.call_count, 3)
                    uniform.assert_called_with(*bounds)
                    self.assertEqual(sleep.await_count, 3)
                    sleep.assert_awaited_with(selected)

    async def test_private_profiles_ignore_old_environment_settings(self):
        old_settings = {
            name: "invalid"
            for name in (
                "SHIPPING_DELAY_MIN_SECONDS",
                "SHIPPING_DELAY_MAX_SECONDS",
                "SHIPPING_NO_RESPONSE_PROBABILITY",
                "SHIPPING_ERROR_PROBABILITY",
            )
        }
        with patch.dict("os.environ", old_settings):
            await self.test_fixed_delay_endpoints_success_tariffs_and_extremes()

    async def test_each_error_occurs_after_its_selected_delay(self):
        for provider_type, bounds, no_response, _, *_ in PROVIDERS:
            entered, release = asyncio.Event(), asyncio.Event()

            async def sleep(delay: float) -> None:
                self.assertEqual(delay, bounds[0])
                entered.set()
                await release.wait()

            with (
                patch.object(simulated_shipping, "_random", return_value=no_response),
                patch.object(simulated_shipping, "_uniform", return_value=bounds[0]),
                patch.object(simulated_shipping, "_sleep", side_effect=sleep),
            ):
                task = asyncio.create_task(provider_type().quote(request()))
                try:
                    await asyncio.wait_for(entered.wait(), 1)
                    self.assertFalse(task.done())
                    release.set()
                    with self.assertRaises(ProviderTechnicalError):
                        await task
                finally:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)

    async def test_each_probability_boundary_and_normalized_outcome_without_retry(self):
        for provider_type, bounds, no_response, error, *_ in PROVIDERS:
            for outcome, expected, code in (
                (0, ProviderStatus.FAILED, ProviderErrorCode.PROVIDER_TIMEOUT),
                (
                    no_response - 0.001,
                    ProviderStatus.FAILED,
                    ProviderErrorCode.PROVIDER_TIMEOUT,
                ),
                (no_response, ProviderStatus.FAILED, ProviderErrorCode.PROVIDER_ERROR),
                (
                    no_response + error - 0.001,
                    ProviderStatus.FAILED,
                    ProviderErrorCode.PROVIDER_ERROR,
                ),
                (no_response + error, ProviderStatus.QUOTED, None),
                (0.99, ProviderStatus.QUOTED, None),
            ):
                with (
                    self.subTest(provider=provider_type.__name__, outcome=outcome),
                    patch.object(
                        simulated_shipping, "_random", return_value=outcome
                    ) as random,
                    patch.object(
                        simulated_shipping, "_uniform", return_value=bounds[0]
                    ) as uniform,
                    patch.object(
                        simulated_shipping, "_sleep", new_callable=AsyncMock
                    ) as sleep,
                ):
                    results = await asyncio.wait_for(
                        ShippingQuoteComparator(
                            [provider_type()], timeout_seconds=0.01
                        ).compare(request()),
                        1,
                    )
                    self.assertEqual(
                        (results[0].status, results[0].error_code), (expected, code)
                    )
                    random.assert_called_once_with()
                    uniform.assert_called_once_with(*bounds)
                    sleep.assert_awaited_once_with(bounds[0])

    async def test_comparison_concurrent_outcomes_are_controlled_without_order_assumptions(
        self,
    ):
        # One common outcome per comparison makes every provider independent of scheduling.
        for outcome, status, error in (
            (0.99, ProviderStatus.QUOTED, None),
            (0.11, ProviderStatus.FAILED, ProviderErrorCode.PROVIDER_ERROR),
            (0, ProviderStatus.FAILED, ProviderErrorCode.PROVIDER_TIMEOUT),
        ):
            # .11 is an error only for Economy and Standard; Express succeeds.
            with (
                patch.object(
                    simulated_shipping, "_random", return_value=outcome
                ) as random,
                patch.object(
                    simulated_shipping, "_uniform", side_effect=lambda low, high: low
                ),
                patch.object(
                    simulated_shipping, "_sleep", new_callable=AsyncMock
                ) as sleep,
            ):
                results = await ShippingQuoteComparator(
                    [item[0]() for item in PROVIDERS], timeout_seconds=0.01
                ).compare(request())
                self.assertEqual(
                    [result.provider_code for result in results],
                    ["sim-economy", "sim-express", "sim-standard"],
                )
                for result in results:
                    express_success = (
                        outcome == 0.11 and result.provider_code == "sim-express"
                    )
                    self.assertEqual(
                        (result.status, result.error_code),
                        (ProviderStatus.QUOTED, None)
                        if express_success
                        else (status, error),
                    )
                self.assertEqual(random.call_count, 3)
                self.assertEqual(sleep.await_count, 3)

    async def test_no_response_is_cancelled_without_detached_tasks(self):
        for provider_type, bounds, *_ in PROVIDERS:
            delayed = asyncio.Event()

            async def sleep(delay: float) -> None:
                delayed.set()

            with (
                patch.object(simulated_shipping, "_random", return_value=0),
                patch.object(simulated_shipping, "_uniform", return_value=bounds[0]),
                patch.object(simulated_shipping, "_sleep", side_effect=sleep),
            ):
                existing = asyncio.all_tasks()
                task = asyncio.create_task(provider_type().quote(request()))
                try:
                    await asyncio.wait_for(delayed.wait(), 1)
                    self.assertFalse(task.done())
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await task
                    self.assertEqual(asyncio.all_tasks(), existing)
                finally:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)

    async def test_cancelling_comparison_cleans_up_active_delays(self):
        for provider_type, bounds, *_ in PROVIDERS:
            entered, cleaned = asyncio.Event(), asyncio.Event()

            async def sleep(delay: float) -> None:
                entered.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cleaned.set()

            with (
                patch.object(simulated_shipping, "_random", return_value=0.99),
                patch.object(simulated_shipping, "_uniform", return_value=bounds[0]),
                patch.object(simulated_shipping, "_sleep", side_effect=sleep),
            ):
                existing = asyncio.all_tasks()
                task = asyncio.create_task(
                    ShippingQuoteComparator([provider_type()]).compare(request())
                )
                try:
                    await asyncio.wait_for(entered.wait(), 1)
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await task
                    self.assertTrue(cleaned.is_set())
                    self.assertEqual(asyncio.all_tasks(), existing)
                finally:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)

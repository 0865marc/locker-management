"""Compare independent providers with bounded, caller-owned asynchronous work."""
import asyncio
from collections.abc import Iterable
from math import isfinite

from application.quotations.models import ProviderResult, ProviderStatus, ProviderErrorCode
from application.quotations.ports import ShippingProvider
from domain.lockers import require_instance
from domain.shipping_quotes import ShippingQuoteRequest, QuoteOffers, NoCoverage, validate_code


async def _provider_response(provider: ShippingProvider, request: ShippingQuoteRequest) -> object:
    """Treat adapter output as untrusted until normalized runtime validation."""
    return await provider.quote(request)


class ShippingQuoteComparator:
    def __init__(
        self,
        providers: Iterable[ShippingProvider],
        *,
        max_concurrency: int = 3,
        timeout_seconds: float = 2.0,
    ) -> None:
        if type(max_concurrency) is not int or max_concurrency < 1:
            raise ValueError('max_concurrency must be a positive integer')
        if (type(timeout_seconds) not in (int, float)
                or not isfinite(timeout_seconds) or timeout_seconds <= 0):
            raise ValueError('timeout_seconds must be a positive finite number')
        configured: list[tuple[str, ShippingProvider]] = []
        codes: set[str] = set()
        for provider in tuple(providers):
            code = provider.code
            validate_code(code, 'provider_code')
            if code in codes:
                raise ValueError('provider_code must be unique')
            codes.add(code)
            configured.append((code, provider))
        if not configured:
            raise ValueError('At least one provider is required')
        self._providers = tuple(sorted(configured, key=lambda item: item[0]))
        self._max_concurrency = max_concurrency
        self._timeout_seconds = timeout_seconds

    async def compare(self, request: ShippingQuoteRequest) -> tuple[ProviderResult, ...]:
        request = require_instance(request, ShippingQuoteRequest, 'request must be ShippingQuoteRequest')
        request.__post_init__()
        # A separate semaphore per invocation bounds this comparison, not other callers.
        slots = asyncio.Semaphore(self._max_concurrency)
        children = [asyncio.create_task(self._quote(code, provider, request, slots))
                    for code, provider in self._providers]
        try:
            return tuple(await asyncio.gather(*children))
        except BaseException:
            for child in children:
                child.cancel()
            await asyncio.gather(*children, return_exceptions=True)
            raise

    async def _quote(
        self,
        code: str,
        provider: ShippingProvider,
        request: ShippingQuoteRequest,
        slots: asyncio.Semaphore,
    ) -> ProviderResult:
        async with slots:
            deadline = asyncio.timeout(self._timeout_seconds)
            try:
                async with deadline:
                    response = await _provider_response(provider, request)
                if isinstance(response, QuoteOffers):
                    # Recheck the adapter boundary, including incorrectly constructed values.
                    response.__post_init__()
                    return ProviderResult(
                        code, ProviderStatus.QUOTED,
                        tuple(sorted(response.offers, key=lambda offer: offer.service_code)))
                if isinstance(response, NoCoverage):
                    return ProviderResult(code, ProviderStatus.NOT_COVERED)
                return ProviderResult(code, ProviderStatus.FAILED,
                                      error_code=ProviderErrorCode.PROVIDER_ERROR)
            except TimeoutError:
                return ProviderResult(
                    code, ProviderStatus.FAILED,
                    error_code=(ProviderErrorCode.PROVIDER_TIMEOUT if deadline.expired()
                                else ProviderErrorCode.PROVIDER_ERROR))
            except Exception:
                # Ordinary adapter failures are isolated. CancelledError propagates.
                return ProviderResult(code, ProviderStatus.FAILED,
                                      error_code=ProviderErrorCode.PROVIDER_ERROR)

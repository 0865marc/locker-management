from collections.abc import Callable
from datetime import datetime
import logging
from uuid import UUID, uuid4

from application.quotations.models import Quotation, QuotationStatus, ProcessErrorCode
from application.quotations.errors import PublicationError, QuotationStorageError, SubmissionError
from application.quotations.ports import QuotationPublisher, QuotationRepository
from application.quotations.comparison import ShippingQuoteComparator
from domain.shipping_quotes import ShippingQuoteRequest

logger = logging.getLogger(__name__)


class QuotationService:
    def __init__(self, repository: QuotationRepository, publisher: QuotationPublisher,
                 clock: Callable[[], datetime]) -> None:
        self.repository = repository
        self.publisher = publisher
        self.clock = clock

    async def submit(self, request: ShippingQuoteRequest) -> Quotation:
        request.__post_init__()
        quotation = Quotation(uuid4(), request, QuotationStatus.PENDING, self.clock())
        await self.repository.save(quotation)
        try:
            await self.publisher.publish(quotation.id)
        except PublicationError as error:
            try:
                await self.repository.fail(quotation.id, QuotationStatus.PENDING,
                                           ProcessErrorCode.PUBLISH_ERROR, self.clock())
            except QuotationStorageError:
                logger.warning('Could not record quotation publication failure')
            raise SubmissionError(quotation.id) from error
        return quotation

    async def get(self, quotation_id: UUID) -> Quotation | None:
        return await self.repository.get(quotation_id)


class QuotationProcessor:
    def __init__(self, repository: QuotationRepository, comparator: ShippingQuoteComparator,
                 clock: Callable[[], datetime]) -> None:
        self.repository = repository
        self.comparator = comparator
        self.clock = clock

    async def process(self, quotation_id: UUID) -> None:
        try:
            quotation = await self.repository.start(quotation_id)
            if quotation is None:
                return
            results = await self.comparator.compare(quotation.request)
            await self.repository.complete(quotation_id, results, self.clock())
        except Exception:
            logger.warning('Quotation processing failed')
            try:
                await self.repository.fail(quotation_id, QuotationStatus.PROCESSING,
                                           ProcessErrorCode.PROCESSING_ERROR, self.clock())
            except QuotationStorageError:
                logger.warning('Could not record quotation processing failure')

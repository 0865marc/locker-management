from uuid import UUID


class QuotationStorageError(Exception):
    """Storage is unavailable or a transaction failed."""


class PublicationError(Exception):
    """Broker publication was not confirmed."""


class SubmissionError(Exception):
    def __init__(self, quotation_id: UUID) -> None:
        super().__init__('Quotation publication failed')
        self.quotation_id = quotation_id


class ProviderTechnicalError(Exception):
    """An expected transport or provider infrastructure failure."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response

from adapters.http.quotations.schemas import (
    QuotationAccepted,
    QuotationInput,
    QuotationResponse,
)
from application.quotation_models import QuotationStorageError, SubmissionError
from application.quotations import QuotationService


def create_quotation_router(service: QuotationService) -> APIRouter:
    router = APIRouter(prefix="/quotations", tags=["quotations"])

    @router.post("", status_code=202, response_model=QuotationAccepted)
    async def submit(payload: QuotationInput, response: Response) -> QuotationAccepted:
        try:
            quotation = await service.submit(payload.domain())
        except SubmissionError as error:
            raise HTTPException(
                503, detail={"code": "PUBLISH_ERROR", "id": str(error.quotation_id)}
            ) from error
        except QuotationStorageError as error:
            raise HTTPException(503, detail="Quotation storage unavailable") from error
        response.headers["Location"] = f"/quotations/{quotation.id}"
        return QuotationAccepted(id=quotation.id, status=quotation.status)

    @router.get("/{id}", response_model=QuotationResponse)
    async def get(id: UUID) -> QuotationResponse:
        try:
            quotation = await service.get(id)
        except QuotationStorageError as error:
            raise HTTPException(503, detail="Quotation storage unavailable") from error
        if quotation is None:
            raise HTTPException(404, detail="Quotation not found")
        return QuotationResponse.model_validate(quotation)

    return router

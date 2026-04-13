"""PDF Summary API router with dependency injection."""

from uuid import UUID
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from app.application.services.summary_service import SummaryService
from app.presentation.schemas.pdf_summary import (
    SummaryResponse,
    SummaryListResponse,
    HealthResponse,
)

router = APIRouter(prefix="/api", tags=["summaries"])


def get_summary_service() -> SummaryService:
    from app.main import get_summary_service as _get_service

    return _get_service()


@router.post("/summarize", response_model=SummaryResponse)
async def summarize_pdf(
    file: UploadFile = File(...),
    service: SummaryService = Depends(get_summary_service),
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    summary = await service.create_summary(content, file.filename)
    return SummaryResponse(
        id=summary.id,
        original_filename=summary.original_filename,
        summary_text=summary.summary_text,
        created_at=summary.created_at,
    )


@router.get("/summaries", response_model=SummaryListResponse)
async def list_summaries(
    limit: int = 100,
    service: SummaryService = Depends(get_summary_service),
):
    summaries = await service.list_summaries(limit)
    return SummaryListResponse(
        summaries=[
            SummaryResponse(
                id=s.id,
                original_filename=s.original_filename,
                summary_text=s.summary_text,
                created_at=s.created_at,
            )
            for s in summaries
        ],
        total=len(summaries),
    )


@router.get("/summaries/{summary_id}", response_model=SummaryResponse)
async def get_summary(
    summary_id: UUID,
    service: SummaryService = Depends(get_summary_service),
):
    summary = await service.get_summary(summary_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    return SummaryResponse(
        id=summary.id,
        original_filename=summary.original_filename,
        summary_text=summary.summary_text,
        created_at=summary.created_at,
    )


@router.get("/health", response_model=HealthResponse)
async def health_check(service: SummaryService = Depends(get_summary_service)):
    ai_available = await service._ai_provider.health_check()
    return HealthResponse(
        status="healthy" if ai_available else "degraded",
        ai_provider_available=ai_available,
    )

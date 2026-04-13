"""FastAPI application entry point with dependency injection."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pathlib import Path

from app.core import get_settings
from app.application.services.pdf_service import PDFService
from app.application.services.summary_service import SummaryService
from app.infrastructure.external.nvidia_client import NvidiaAIProvider
from app.infrastructure.repositories.in_memory_repository import (
    InMemorySummaryRepository,
)
from app.presentation.routers.pdf_summary import router as pdf_router


_summary_service: SummaryService | None = None


def get_summary_service() -> SummaryService:
    if _summary_service is None:
        raise RuntimeError("Application not initialized")
    return _summary_service


def create_summary_service() -> SummaryService:
    global _summary_service
    _summary_service = SummaryService(
        pdf_service=PDFService(),
        ai_provider=NvidiaAIProvider(),
        repository=InMemorySummaryRepository(),
    )
    return _summary_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_summary_service()
    get_settings().upload_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title=get_settings().app_name,
    description="Upload PDF files and generate AI-powered summaries",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(pdf_router)


@app.get("/", response_class=HTMLResponse)
async def root():
    template_path = Path(__file__).parent / "presentation" / "templates" / "index.html"
    return template_path.read_text()

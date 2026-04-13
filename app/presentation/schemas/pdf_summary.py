"""Pydantic schemas for PDF summary operations."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class SummaryRequest(BaseModel):
    max_length: int = Field(default=500, ge=100, le=2000)


class SummaryResponse(BaseModel):
    id: UUID
    original_filename: str
    summary_text: str
    created_at: datetime


class SummaryListResponse(BaseModel):
    summaries: list[SummaryResponse]
    total: int


class HealthResponse(BaseModel):
    status: str
    ai_provider_available: bool

"""Application layer interfaces (ports)."""

from app.application.interfaces.ai_provider import AIProvider
from app.application.interfaces.summary_repository import SummaryRepository

__all__ = ["AIProvider", "SummaryRepository"]

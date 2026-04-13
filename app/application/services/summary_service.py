"""Summary generation service - orchestrates PDF extraction and AI summarization."""

from app.application.interfaces.ai_provider import AIProvider, AIResponse
from app.application.interfaces.summary_repository import Summary, SummaryRepository
from app.application.services.pdf_service import PDFService, ExtractedPDF


class SummaryService:
    def __init__(
        self,
        pdf_service: PDFService,
        ai_provider: AIProvider,
        repository: SummaryRepository,
    ):
        self._pdf_service = pdf_service
        self._ai_provider = ai_provider
        self._repository = repository

    async def create_summary(self, file_content: bytes, filename: str) -> Summary:
        extracted = self._pdf_service.extract_text(file_content, filename)
        ai_response = await self._ai_provider.generate_summary(extracted.text)

        summary = Summary(
            id=None,
            original_filename=filename,
            summary_text=ai_response.content,
            extracted_text=extracted.text[:1000],
            created_at=None,
        )
        return await self._repository.save(summary)

    async def get_summary(self, summary_id) -> Summary | None:
        return await self._repository.get_by_id(summary_id)

    async def list_summaries(self, limit: int = 100) -> list[Summary]:
        return await self._repository.get_all(limit)

import asyncio
import hashlib
from typing import List

from App.domain.exceptions import FileTooLargeError, InvalidPdfError
from App.domain.interfaces import IDocumentCache, IPdfExtractor
from App.domain.models import ExtractedPage, PdfExtractionResponse


class PdfExtractionService:
    def __init__(self, extractor: IPdfExtractor, repository: IDocumentCache, max_file_size_mb: int):
        self.extractor = extractor
        self.repository = repository
        self.max_file_size_mb = max_file_size_mb

    async def process_pdf(self, filename: str, file_bytes: bytes) -> PdfExtractionResponse:
        self._validate(filename, file_bytes)
        checksum = hashlib.sha256(file_bytes).hexdigest()

        # Si el mismo archivo ya se procesó, se devuelve lo guardado (caché).
        existing_doc = await self.repository.get_by_checksum(checksum)
        if existing_doc:
            return self._build_response(existing_doc["filename"], existing_doc["pages"])

        # La extracción ocupa la CPU: se corre en un hilo aparte para no
        # frenar el event loop mientras tanto.
        pages = await asyncio.to_thread(self.extractor.extract_text, file_bytes)
        response = self._build_response(filename, pages)

        await self.repository.save_document({"checksum": checksum, **response.model_dump()})
        return response

    def _validate(self, filename: str, file_bytes: bytes) -> None:
        if not filename.lower().endswith(".pdf"):
            raise InvalidPdfError("El archivo no es un PDF válido.")

        if len(file_bytes) > self.max_file_size_mb * 1024 * 1024:
            raise FileTooLargeError(f"El archivo supera el límite de {self.max_file_size_mb} MB.")

    @staticmethod
    def _build_response(filename: str, pages: List[ExtractedPage | dict]) -> PdfExtractionResponse:
        # pages llega como modelos (recién extraído) o como diccionarios
        # (leído de MongoDB); Pydantic acepta las dos formas.
        return PdfExtractionResponse(filename=filename, total_pages=len(pages), pages=pages)

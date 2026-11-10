from App.core.config import settings
from App.infrastructure.pymupdf_extractor import PyMuPdfExtractor
from App.infrastructure.mongo_repository import MongoDocumentRepository
from App.services.pdf_service import PdfExtractionService

def get_pdf_service() -> PdfExtractionService:
    return PdfExtractionService(
        extractor=PyMuPdfExtractor(),
        repository=MongoDocumentRepository(),
        max_file_size_mb=settings.MAX_FILE_SIZE_MB,
    )

def get_document_repository() -> MongoDocumentRepository:
    """Provee la conexión a la base de datos para el CRUD."""
    return MongoDocumentRepository()

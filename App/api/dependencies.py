from fastapi import Request

from App.domain.interfaces import IDocumentRepository
from App.infrastructure.pymupdf_extractor import PyMuPdfExtractor
from App.services.pdf_service import PdfExtractionService

# La configuración y el repositorio se crean una sola vez al armar la
# aplicación (App/main.py) y quedan en app.state; acá solo se reparten.

def get_pdf_service(request: Request) -> PdfExtractionService:
    return PdfExtractionService(
        extractor=PyMuPdfExtractor(),
        repository=request.app.state.repository,
        max_file_size_mb=request.app.state.settings.MAX_FILE_SIZE_MB,
    )

def get_document_repository(request: Request) -> IDocumentRepository:
    """Provee la conexión a la base de datos para el CRUD."""
    return request.app.state.repository

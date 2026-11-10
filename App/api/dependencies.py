from App.infrastructure.pymupdf_extractor import PyMuPdfExtractor
from App.infrastructure.mongo_repository import MongoDocumentRepository
from App.services.pdf_service import PdfExtractionService

def get_pdf_service() -> PdfExtractionService:
    extractor = PyMuPdfExtractor()
    repository = MongoDocumentRepository() # Instanciamos la conexión a Mongo
    
    # Ahora nuestro servicio recibirá el extractor y la base de datos
    return PdfExtractionService(extractor=extractor, repository=repository)

def get_document_repository() -> MongoDocumentRepository:
    """Provee la conexión a la base de datos para el CRUD."""
    return MongoDocumentRepository()

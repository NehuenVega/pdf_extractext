import pytest
from App.services.pdf_service import PdfExtractionService
from App.domain.interfaces import IPdfExtractor, IDocumentRepository

# 1. Repositorio Falso Actualizado (ahora devuelve un documento completo)
class FakeRepository(IDocumentRepository):
    def __init__(self, existing_checksum=None):
        self.existing_checksum = existing_checksum

    async def save_document(self, document_data: dict) -> str:
        return "fake_id_123"

    async def get_by_checksum(self, checksum: str):
        if checksum == self.existing_checksum:
            # Ahora simulamos la estructura completa que espera la caché
            return {
                "_id": "fake_id_123", 
                "checksum": checksum,
                "filename": "apunte_viejo.pdf",
                "total_pages": 1,
                "pages": [{"page_number": 1, "content": "Texto en caché"}]
            }
        return None
        
    async def get_all(self): return []
    async def get_by_id(self, doc_id: str): return None
    async def update(self, doc_id: str, update_data: dict): return False
    async def delete(self, doc_id: str): return False

# 2. Extractor Falso
class FakeExtractor(IPdfExtractor):
    def extract_text(self, file_bytes: bytes):
        return []

@pytest.mark.asyncio
async def test_retornar_documento_cacheado():
    """Prueba que si el documento ya existe, se devuelve desde la base de datos (Caché)."""
    pdf_bytes = b"Hola UTN"
    import hashlib
    checksum_esperado = hashlib.sha256(pdf_bytes).hexdigest()

    # Preparamos el repositorio simulando que ese Checksum YA EXISTE
    repo = FakeRepository(existing_checksum=checksum_esperado)
    extractor = FakeExtractor()
    service = PdfExtractionService(extractor=extractor, repository=repo)

    # Llamamos al servicio con el mismo archivo
    response = await service.process_pdf("apunte_nuevo.pdf", pdf_bytes)
    
    # VERIFICAMOS LA CACHÉ: El nombre del archivo en la respuesta debe ser 
    # el que estaba guardado ("apunte_viejo.pdf"), no el que le mandamos ("apunte_nuevo.pdf")
    assert response.filename == "apunte_viejo.pdf"
    assert response.total_pages == 1
    assert response.pages[0].content == "Texto en caché"

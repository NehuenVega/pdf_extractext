import hashlib

import pytest
from App.services.pdf_service import PdfExtractionService
from App.domain.exceptions import FileTooLargeError, InvalidPdfError, UnreadablePdfError
from App.domain.interfaces import IPdfExtractor, IDocumentRepository
from App.domain.models import ExtractedPage

# 1. Repositorio Falso: guarda en memoria lo que el servicio persiste
class FakeRepository(IDocumentRepository):
    def __init__(self, existing_checksum=None):
        self.existing_checksum = existing_checksum
        self.saved = []

    async def save_document(self, document_data: dict) -> str:
        self.saved.append(document_data)
        return "fake_id_123"

    async def get_by_checksum(self, checksum: str):
        if checksum == self.existing_checksum:
            # Simulamos la estructura completa que espera la caché
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

# 2. Extractores Falsos
class FakeExtractor(IPdfExtractor):
    def __init__(self, pages=None):
        self.pages = pages or []
        self.calls = 0

    def extract_text(self, file_bytes: bytes):
        self.calls += 1
        return self.pages

class BrokenPdfExtractor(IPdfExtractor):
    def extract_text(self, file_bytes: bytes):
        raise UnreadablePdfError("El PDF está dañado o no se puede leer.")


def build_service(repository=None, extractor=None, max_file_size_mb=1):
    return PdfExtractionService(
        extractor=extractor or FakeExtractor(),
        repository=repository or FakeRepository(),
        max_file_size_mb=max_file_size_mb,
    )


async def test_retornar_documento_cacheado():
    """Prueba que si el documento ya existe, se devuelve desde la base de datos (Caché)."""
    pdf_bytes = b"Hola UTN"
    checksum_esperado = hashlib.sha256(pdf_bytes).hexdigest()

    # Preparamos el repositorio simulando que ese Checksum YA EXISTE
    extractor = FakeExtractor()
    service = build_service(FakeRepository(existing_checksum=checksum_esperado), extractor)

    # Llamamos al servicio con el mismo archivo
    response = await service.process_pdf("apunte_nuevo.pdf", pdf_bytes)

    # VERIFICAMOS LA CACHÉ: El nombre del archivo en la respuesta debe ser
    # el que estaba guardado ("apunte_viejo.pdf"), no el que le mandamos ("apunte_nuevo.pdf")
    assert response.filename == "apunte_viejo.pdf"
    assert response.total_pages == 1
    assert response.pages[0].content == "Texto en caché"
    assert extractor.calls == 0


async def test_documento_nuevo_se_extrae_y_se_guarda():
    """Si el checksum no existe, se extrae el texto y se persiste con su checksum."""
    pages = [ExtractedPage(page_number=1, content="Hola"), ExtractedPage(page_number=2, content="UTN")]
    repository = FakeRepository()
    service = build_service(repository, FakeExtractor(pages))

    response = await service.process_pdf("apunte.pdf", b"Hola UTN")

    assert response.filename == "apunte.pdf"
    assert response.total_pages == 2
    (saved,) = repository.saved
    assert saved["checksum"] == hashlib.sha256(b"Hola UTN").hexdigest()
    assert saved["pages"] == [{"page_number": 1, "content": "Hola"}, {"page_number": 2, "content": "UTN"}]


@pytest.mark.parametrize("filename", ["apunte.docx", "apunte", ""])
async def test_rechaza_archivos_sin_extension_pdf(filename):
    with pytest.raises(InvalidPdfError):
        await build_service().process_pdf(filename, b"%PDF-1.7")


async def test_acepta_extension_pdf_en_mayusculas():
    response = await build_service().process_pdf("APUNTE.PDF", b"%PDF-1.7")

    assert response.filename == "APUNTE.PDF"


async def test_rechaza_archivos_que_superan_el_limite():
    service = build_service(max_file_size_mb=1)

    with pytest.raises(FileTooLargeError, match="1 MB"):
        await service.process_pdf("grande.pdf", b"0" * (1024 * 1024 + 1))


async def test_pdf_danado_no_se_guarda():
    repository = FakeRepository()
    service = build_service(repository, BrokenPdfExtractor())

    with pytest.raises(UnreadablePdfError):
        await service.process_pdf("roto.pdf", b"%PDF-1.7 roto")
    assert repository.saved == []

import pymupdf
import pytest
from fastapi.testclient import TestClient
from App.main import create_app
from App.api.dependencies import get_document_repository, get_pdf_service
from App.core.config import Settings
from App.domain.interfaces import IDocumentRepository
from App.infrastructure.pymupdf_extractor import PyMuPdfExtractor
from App.services.pdf_service import PdfExtractionService

# 1. Creamos un Repositorio Falso para no afectar el MongoDB real
class MockRepository(IDocumentRepository):
    def __init__(self):
        # Simulamos que la BD ya tiene un documento guardado
        self.docs = {
            "doc_123": {
                "_id": "doc_123",
                "filename": "apunte_algebra.pdf",
                "checksum": "hash_falso",
                "pages": [],
                "total_pages": 1
            }
        }
        self.saved = []

    async def save_document(self, document_data: dict) -> str:
        self.saved.append(document_data)
        return "doc_nuevo"

    async def get_by_checksum(self, checksum: str):
        return None

    async def get_all(self):
        return list(self.docs.values())

    async def get_by_id(self, doc_id: str):
        return self.docs.get(doc_id)

    async def update(self, doc_id: str, update_data: dict):
        if doc_id in self.docs:
            self.docs[doc_id].update(update_data)
            return True
        return False

    async def delete(self, doc_id: str):
        if doc_id in self.docs:
            del self.docs[doc_id]
            return True
        return False

# 2. Cada test arma su propia app con un repositorio nuevo: así ningún test
# depende de lo que modificó otro (antes compartían un único MockRepository).
@pytest.fixture
def repository():
    return MockRepository()

@pytest.fixture
def client(repository):
    app = create_app(Settings(MAX_FILE_SIZE_MB=1))
    app.dependency_overrides[get_document_repository] = lambda: repository
    app.dependency_overrides[get_pdf_service] = lambda: PdfExtractionService(
        extractor=PyMuPdfExtractor(), repository=repository, max_file_size_mb=1
    )
    return TestClient(app)

def build_pdf(text: str) -> bytes:
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), text)
    return document.tobytes()

# --- TESTS DEL CRUD ---

def test_list_documents(client):
    """Prueba que el endpoint GET / devuelve la lista de documentos."""
    response = client.get("/api/v1/documents/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["documents"][0]["filename"] == "apunte_algebra.pdf"

def test_get_document_by_id_success(client):
    """Prueba que buscar un ID existente devuelve el documento."""
    response = client.get("/api/v1/documents/doc_123")
    assert response.status_code == 200
    assert response.json()["filename"] == "apunte_algebra.pdf"

def test_get_document_by_id_not_found(client):
    """Prueba que buscar un ID que no existe devuelve error 404."""
    response = client.get("/api/v1/documents/doc_999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Documento no encontrado"

def test_update_document(client, repository):
    """Prueba que se puede actualizar el nombre del archivo."""
    response = client.patch("/api/v1/documents/doc_123?new_filename=apunte_modificado.pdf")
    assert response.status_code == 200
    assert response.json()["message"] == "Documento actualizado correctamente"
    assert repository.docs["doc_123"]["filename"] == "apunte_modificado.pdf"

def test_update_document_not_found(client):
    response = client.patch("/api/v1/documents/doc_999?new_filename=x.pdf")
    assert response.status_code == 404

def test_delete_document(client, repository):
    """Prueba que se puede borrar un documento existente."""
    response = client.delete("/api/v1/documents/doc_123")
    assert response.status_code == 200
    assert response.json()["message"] == "Documento eliminado correctamente"
    assert "doc_123" not in repository.docs

def test_delete_document_twice_returns_404(client):
    client.delete("/api/v1/documents/doc_123")
    response = client.delete("/api/v1/documents/doc_123")
    assert response.status_code == 404

# --- TESTS DE EXTRACCIÓN DE TEXTO ---

def test_extract_text_returns_pages_and_saves_document(client, repository):
    files = {"file": ("apunte.pdf", build_pdf("Hola UTN"), "application/pdf")}
    response = client.post("/api/v1/extract-text", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "apunte.pdf"
    assert data["total_pages"] == 1
    assert data["pages"][0]["content"].strip() == "Hola UTN"
    assert len(repository.saved) == 1

@pytest.mark.parametrize(
    ("filename", "content", "status"),
    [
        pytest.param("apunte.txt", b"texto", 400, id="extension"),
        pytest.param("grande.pdf", b"0" * (1024 * 1024 + 1), 413, id="tamano"),
        pytest.param("roto.pdf", b"%PDF-1.7 contenido roto", 422, id="pdf-roto"),
    ],
)
def test_extract_text_errors_are_translated_to_http(client, filename, content, status):
    files = {"file": (filename, content, "application/pdf")}
    response = client.post("/api/v1/extract-text", files=files)
    assert response.status_code == status
    assert isinstance(response.json()["detail"], str)

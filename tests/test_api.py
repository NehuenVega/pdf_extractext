import pytest
from fastapi.testclient import TestClient
from App.main import app
from App.api.dependencies import get_document_repository
from App.domain.interfaces import IDocumentRepository

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

    async def save_document(self, document_data: dict) -> str:
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

# 2. Le decimos a FastAPI que use nuestro Mock en lugar del repositorio real
app.dependency_overrides[get_document_repository] = lambda: MockRepository()

# 3. Inicializamos el cliente de pruebas
client = TestClient(app)

# --- EMPIEZAN LOS TESTS DEL CRUD ---

def test_list_documents():
    """Prueba que el endpoint GET / devuelve la lista de documentos."""
    response = client.get("/api/v1/documents/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["documents"][0]["filename"] == "apunte_algebra.pdf"

def test_get_document_by_id_success():
    """Prueba que buscar un ID existente devuelve el documento."""
    response = client.get("/api/v1/documents/doc_123")
    assert response.status_code == 200
    assert response.json()["filename"] == "apunte_algebra.pdf"

def test_get_document_by_id_not_found():
    """Prueba que buscar un ID que no existe devuelve error 404."""
    response = client.get("/api/v1/documents/doc_999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Documento no encontrado"

def test_update_document():
    """Prueba que se puede actualizar el nombre del archivo."""
    response = client.patch("/api/v1/documents/doc_123?new_filename=apunte_modificado.pdf")
    assert response.status_code == 200
    assert response.json()["message"] == "Documento actualizado correctamente"

def test_delete_document():
    """Prueba que se puede borrar un documento existente."""
    response = client.delete("/api/v1/documents/doc_123")
    assert response.status_code == 200
    assert response.json()["message"] == "Documento eliminado correctamente"

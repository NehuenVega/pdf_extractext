from typing import Protocol, List, Optional
from App.domain.models import ExtractedPage

class IPdfExtractor(Protocol):
    def extract_text(self, file_bytes: bytes) -> List[ExtractedPage]:
        ...

# NUEVA INTERFAZ PARA LA BASE DE DATOS
class IDocumentRepository(Protocol):
    async def save_document(self, document_data: dict) -> str:
        """Guarda el documento y retorna el ID insertado."""
        ...
        
    async def get_by_checksum(self, checksum: str) -> Optional[dict]:
        """Busca si un documento ya existe mediante su checksum."""
        ...
    async def get_all(self) -> List[dict]:
        """Devuelve todos los documentos guardados."""
        ...
        
    async def get_by_id(self, doc_id: str) -> Optional[dict]:
        """Busca un documento por su ID único."""
        ...
        
    async def update(self, doc_id: str, update_data: dict) -> bool:
        """Actualiza campos de un documento. Retorna True si tuvo éxito."""
        ...
        
    async def delete(self, doc_id: str) -> bool:
        """Borra un documento. Retorna True si tuvo éxito."""
        ...

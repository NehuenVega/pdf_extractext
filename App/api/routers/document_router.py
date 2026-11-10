from fastapi import APIRouter, Depends, HTTPException
from typing import List
# Reutilizamos el repositorio inyectado
from App.api.dependencies import get_document_repository 
from App.domain.interfaces import IDocumentRepository

router = APIRouter(prefix="/v1/documents", tags=["Documents CRUD"])

@router.get("/")
async def list_documents(repo: IDocumentRepository = Depends(get_document_repository)):
    """Lista todos los PDFs procesados."""
    docs = await repo.get_all()
    return {"total": len(docs), "documents": docs}

@router.get("/{doc_id}")
async def get_document(doc_id: str, repo: IDocumentRepository = Depends(get_document_repository)):
    """Trae el detalle de un PDF por su ID."""
    doc = await repo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return doc

@router.patch("/{doc_id}")
async def update_document(doc_id: str, new_filename: str, repo: IDocumentRepository = Depends(get_document_repository)):
    """Actualiza el nombre del archivo guardado."""
    success = await repo.update(doc_id, {"filename": new_filename})
    if not success:
        raise HTTPException(status_code=404, detail="Documento no encontrado o sin cambios")
    return {"message": "Documento actualizado correctamente"}

@router.delete("/{doc_id}")
async def delete_document(doc_id: str, repo: IDocumentRepository = Depends(get_document_repository)):
    """Elimina un documento de la base de datos."""
    success = await repo.delete(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return {"message": "Documento eliminado correctamente"}

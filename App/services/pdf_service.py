import hashlib
from fastapi import HTTPException
from App.domain.interfaces import IPdfExtractor, IDocumentRepository
from App.domain.models import PdfExtractionResponse
from App.core.config import settings

class PdfExtractionService:
    def __init__(self, extractor, repository): # <--- Asegúrate de tener estos parámetros
        self.extractor = extractor
        self.repository = repository

    # Transformamos la función en asíncrona (async)
    async def process_pdf(self, filename: str, file_bytes: bytes) -> PdfExtractionResponse:
        # 1. Validaciones básicas
        if not filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="El archivo no es un PDF válido.")
        
        max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise HTTPException(status_code=413, detail=f"El archivo supera el límite de {settings.MAX_FILE_SIZE_MB} MB.")

        # 2. Calcular Checksum (SHA-256)
        checksum = hashlib.sha256(file_bytes).hexdigest()

# 3. Verificar duplicados en la base de datos (¡Ahora funciona como Caché!)
        existing_doc = await self.repository.get_by_checksum(checksum)
        if existing_doc:
            # En lugar de lanzar un Error 409, devolvemos la info ya procesada
            return PdfExtractionResponse(
                filename=existing_doc["filename"],
                total_pages=existing_doc["total_pages"],
                # existing_doc["pages"] ya es una lista de diccionarios que Pydantic entiende
                pages=existing_doc["pages"] 
            )

        # 4. Extraer texto usando PyMuPDF
        try:
            pages = self.extractor.extract_text(file_bytes)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error procesando PDF: {str(e)}")

        # 5. Persistir en MongoDB
        document_data = {
            "filename": filename,
            "checksum": checksum,
            "total_pages": len(pages),
            # Convertimos los objetos Pydantic a diccionarios para que Mongo los entienda
            "pages": [p.model_dump() for p in pages] 
        }
        await self.repository.save_document(document_data)

        # 6. Retornar respuesta al cliente
        return PdfExtractionResponse(
            filename=filename,
            total_pages=len(pages),
            pages=pages
        )

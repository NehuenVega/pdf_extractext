from fastapi import APIRouter, UploadFile, File, Depends
from App.services.pdf_service import PdfExtractionService
from App.api.dependencies import get_pdf_service
from App.domain.models import PdfExtractionResponse

router = APIRouter(tags=["Extracción"])


@router.post("/extract-text", response_model=PdfExtractionResponse, summary="Extraer texto por página")
async def extract_text(
    file: UploadFile = File(...),
    service: PdfExtractionService = Depends(get_pdf_service)
):
    """Devuelve el texto de cada página. Si el mismo archivo ya se subió, lo devuelve de MongoDB."""
    content = await file.read()
    # Un upload puede llegar sin nombre de archivo: se valida como "".
    return await service.process_pdf(file.filename or "", content)

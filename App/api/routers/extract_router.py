from fastapi import APIRouter, UploadFile, File, Depends
from App.services.pdf_service import PdfExtractionService
from App.api.dependencies import get_pdf_service
from App.domain.models import PdfExtractionResponse

router = APIRouter(prefix="/v1")


@router.post("/extract-text", response_model=PdfExtractionResponse)
async def extract_text(
    file: UploadFile = File(...),
    service: PdfExtractionService = Depends(get_pdf_service)
):
    content = await file.read()
    
    # ¡Agregamos el 'await' aquí!
    return await service.process_pdf(file.filename, content)

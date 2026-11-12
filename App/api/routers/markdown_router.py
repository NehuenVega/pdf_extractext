"""POST /extract (PDF → Markdown) y GET /health.

Son las rutas que usa el balanceador y las pruebas de carga, por eso van en la
raíz y no bajo /api/v1. El handler solo coordina: lee el upload y delega la
extracción al servicio, que la corre en el pool de procesos. No hace trabajo
pesado propio, así el event loop queda libre para atender más conexiones.
"""

from fastapi import APIRouter, Depends, Request, Response

from App.api.dependencies import get_markdown_service
from App.api.uploads import read_pdf_upload
from App.domain.models import MarkdownExtractionResponse
from App.services.markdown_service import MarkdownExtractionService

router = APIRouter()

# El body se lee a mano (ver App/api/uploads.py), así que FastAPI no puede
# deducir su formato: se declara acá para que aparezca en /docs.
PDF_REQUEST_BODY = {
    "required": True,
    "content": {
        "application/pdf": {"schema": {"type": "string", "format": "binary"}},
        "multipart/form-data": {
            "schema": {
                "type": "object",
                "properties": {"file": {"type": "string", "format": "binary"}},
                "required": ["file"],
            }
        },
    },
}


@router.post(
    "/extract",
    response_model=MarkdownExtractionResponse,
    tags=["Markdown"],
    summary="Convertir PDF a Markdown",
    openapi_extra={"requestBody": PDF_REQUEST_BODY},
)
async def extract_markdown(
    request: Request,
    service: MarkdownExtractionService = Depends(get_markdown_service),
) -> Response:
    """Recibe un PDF (binario o multipart) y devuelve ``{"content", "page_count"}``."""
    settings = request.app.state.settings
    pdf = await read_pdf_upload(request, settings.max_file_size_bytes, settings.UPLOAD_TIMEOUT_SECONDS)
    result = await service.extract(pdf)

    queue_ms, extract_ms = result.queue_seconds * 1000, result.extract_seconds * 1000
    # Datos extra para la línea del log de acceso (App/api/access_log.py).
    request.state.log_fields = {
        "pdf_bytes": len(pdf),
        "page_count": result.page_count,
        "queue_ms": round(queue_ms, 1),
        "extract_ms": round(extract_ms, 1),
    }
    # Server-Timing es un encabezado estándar (W3C) para informar en qué se
    # fue el tiempo del lado del servidor: separa la espera en cola del
    # procesamiento al analizar las pruebas de carga.
    headers = {"Server-Timing": f"queue;dur={queue_ms:.1f}, extract;dur={extract_ms:.1f}"}
    return Response(result.body, media_type="application/json", headers=headers)


@router.get("/health", tags=["Estado"], summary="Chequeo de salud")
async def health(service: MarkdownExtractionService = Depends(get_markdown_service)) -> dict:
    """Lo usa el balanceador para saber si la réplica está viva."""
    return {"status": "ok", "running": service.admission.running, "waiting": service.admission.waiting}

"""Traducción de los errores de la aplicación a respuestas HTTP.

Todas las respuestas de error usan el formato de FastAPI, ``{"detail": "..."}``
(también los 503 que genera HAProxy), así el cliente las interpreta igual sin
importar qué endpoint falló.

| Código | Cuándo                                                        |
|--------|---------------------------------------------------------------|
| 400    | No es un PDF, el pedido está vacío o el multipart está mal    |
| 408    | El archivo no llegó completo en UPLOAD_TIMEOUT_SECONDS        |
| 413    | El archivo supera MAX_FILE_SIZE_MB                            |
| 422    | Es un PDF, pero está dañado o tiene contraseña                |
| 499    | El cliente cortó antes de enviar todo (solo queda en el log)  |
| 500    | Murió el proceso de extracción o hubo un error inesperado     |
| 503    | Backpressure: cola llena o espera vencida (con Retry-After)   |
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from App.domain.exceptions import (
    FileTooLargeError,
    InvalidPdfError,
    ServiceOverloadedError,
    UnreadablePdfError,
    WorkerCrashedError,
)

# Segundos que sugerimos esperar antes de reintentar cuando hay saturación.
# Es corto a propósito: las colas se vacían en pocos segundos.
RETRY_AFTER_SECONDS = 2

# Mensajes que Starlette pone solo (ruta o método inexistente), en castellano
# como el resto de la API.
SPANISH_HTTP_DETAILS = {
    "Not Found": "No encontrado.",
    "Method Not Allowed": "Método no permitido.",
}

STATUS_BY_ERROR: dict[type[Exception], int] = {
    InvalidPdfError: 400,
    FileTooLargeError: 413,
    UnreadablePdfError: 422,
    WorkerCrashedError: 500,
    ServiceOverloadedError: 503,
}


def register_exception_handlers(app: FastAPI) -> None:
    for error_type, status in STATUS_BY_ERROR.items():
        app.add_exception_handler(error_type, _handler_for(status))
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(Exception, _unexpected)


def _handler_for(status: int):
    headers = {"Retry-After": str(RETRY_AFTER_SECONDS)} if status == 503 else None

    async def handler(_: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=status, content={"detail": str(error)}, headers=headers)

    return handler


async def _http_error(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, StarletteHTTPException)
    detail = SPANISH_HTTP_DETAILS.get(error.detail, error.detail)
    # Se conservan los encabezados (por ejemplo, Allow en un 405).
    return JSONResponse(status_code=error.status_code, content={"detail": detail}, headers=error.headers)


async def _unexpected(_: Request, error: Exception) -> JSONResponse:
    # No se registra acá: Starlette vuelve a lanzar la excepción después de
    # responder y uvicorn la escribe en el log con su traceback completo.
    # Al cliente nunca le mostramos detalles internos.
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor."})

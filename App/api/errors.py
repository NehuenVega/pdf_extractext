"""Traducción de los errores de la aplicación a respuestas HTTP.

Todas las respuestas de error usan el formato de FastAPI, ``{"detail": "..."}``,
así el cliente las interpreta igual sin importar qué endpoint falló.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from App.domain.exceptions import FileTooLargeError, InvalidPdfError, UnreadablePdfError

STATUS_BY_ERROR: dict[type[Exception], int] = {
    InvalidPdfError: 400,
    FileTooLargeError: 413,
    UnreadablePdfError: 422,
}


def register_exception_handlers(app: FastAPI) -> None:
    for error_type, status in STATUS_BY_ERROR.items():
        app.add_exception_handler(error_type, _handler_for(status))


def _handler_for(status: int):
    async def handler(_: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=status, content={"detail": str(error)})

    return handler

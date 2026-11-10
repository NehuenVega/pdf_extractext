"""Punto de entrada del contenedor: ``python -m App``.

Valida la configuración, deja los logs en JSON y levanta uvicorn con un solo
proceso de event loop (el paralelismo de la extracción lo dan los workers).
"""

import sys

import uvicorn
from pydantic import ValidationError

from App.core.config import get_settings
from App.core.logs import configure_logging


def main() -> None:
    try:
        settings = get_settings()
    except ValidationError as error:
        sys.exit(f"Configuración inválida:\n{error}")

    configure_logging(settings.LOG_LEVEL)
    uvicorn.run(
        # Se pasa como texto para que la app se importe recién acá, con la
        # configuración ya validada.
        "App.main:app",
        host=settings.HOST,
        port=settings.PORT,
        log_config=None,  # usamos nuestra configuración de logs (JSON)
        access_log=False,  # el log de acceso lo escribe AccessLogMiddleware
        server_header=False,
        # Tope de conexiones simultáneas: lo que se procesa + lo que puede
        # esperar + margen para health checks y uploads en curso. Acota la
        # memoria aunque alguien le pegue directo a la réplica, sin proxy.
        limit_concurrency=settings.EXTRACTION_WORKERS + settings.MAX_QUEUE_SIZE + 8,
    )


if __name__ == "__main__":
    main()

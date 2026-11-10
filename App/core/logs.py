"""Logs estructurados en JSON a stdout (Twelve-Factor, XI: logs como flujo).

El servicio no maneja archivos de log: escribe una línea JSON por evento en
stdout y Docker se encarga de juntarlas (``docker compose logs``). En JSON
porque así se pueden filtrar y agregar fácilmente durante el análisis de las
pruebas de carga (por ejemplo, tiempos de cola vs. tiempos de extracción).

Para sumar campos a una línea de log se usa ``extra={"fields": {...}}``.
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime

import orjson


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        entry.update(getattr(record, "fields", {}))
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return orjson.dumps(entry, default=str).decode()


def configure_logging(level: str) -> None:
    """Manda todos los logs (los nuestros y los de uvicorn) a stdout en JSON."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)

    # uvicorn trae sus propios handlers: los sacamos para que sus mensajes
    # pasen por el nuestro. El log de acceso lo escribe nuestro middleware
    # (con más datos), así que el de uvicorn se desactiva.
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True
    logging.getLogger("uvicorn.access").disabled = True

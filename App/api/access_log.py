"""Middleware que escribe una línea de log JSON por cada pedido HTTP.

Es un middleware ASGI "puro" (sin ``BaseHTTPMiddleware``) porque es más
liviano: no envuelve la respuesta, solo mira el código de estado al pasar.

Los handlers pueden sumar datos propios del pedido (tiempo en cola, tiempo
de extracción, páginas) guardándolos en ``request.state.log_fields``.
"""

from __future__ import annotations

import logging
import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("App.access")

# Los health checks del balanceador llegan cada pocos segundos desde cada
# proxy: en INFO taparían los pedidos reales, así que van en DEBUG.
QUIET_PATHS = frozenset({"/health"})


class AccessLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()
        # Si la aplicación falla antes de responder, el servidor contesta 500.
        status = 500

        async def send_and_capture_status(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_and_capture_status)
        finally:
            fields = {
                "method": scope["method"],
                "path": scope["path"],
                "status": status,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                **scope.get("state", {}).get("log_fields", {}),
            }
            level = logging.DEBUG if scope["path"] in QUIET_PATHS else logging.INFO
            logger.log(level, "request", extra={"fields": fields})

"""Control de admisión: limita la concurrencia y aplica backpressure.

Problema que resuelve (consigna, punto 5.2): si llegan más pedidos de los que
la réplica puede procesar, una cola sin límite crece hasta que los pedidos
del final esperan más que el timeout del cliente. Esos pedidos se procesan
igual, gastan CPU y su respuesta ya no le sirve a nadie (en la prueba de
Vegeta del profesor: 501 timeouts).

Solución: una cola acotada en tamaño **y** en tiempo.

- Como mucho ``max_concurrent`` pedidos se procesan a la vez (uno por worker).
- Como mucho ``max_waiting`` pedidos esperan. Si la cola está llena, el
  pedido se rechaza en el momento con ``QueueFullError``.
- Si un pedido espera más de ``wait_timeout`` segundos, se descarta con
  ``QueueTimeoutError`` sin llegar a procesarse.

La capa HTTP traduce ambos errores a ``503 Service Unavailable`` con
``Retry-After``: el cliente se entera enseguida y puede reintentar.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from App.domain.exceptions import QueueFullError, QueueTimeoutError


class AdmissionController:
    def __init__(self, max_concurrent: int, max_waiting: int, wait_timeout: float) -> None:
        self._slots = asyncio.Semaphore(max_concurrent)
        self._max_waiting = max_waiting
        self._wait_timeout = wait_timeout
        self.waiting = 0
        self.running = 0

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[float]:
        """Espera un lugar para procesar; devuelve los segundos que esperó.

        Uso::

            async with admission.slot() as queued_seconds:
                ...  # trabajo pesado

        Raises:
            QueueFullError: si no hay lugar libre y la cola está llena.
            QueueTimeoutError: si no se liberó un lugar a tiempo.
        """
        if self._slots.locked() and self.waiting >= self._max_waiting:
            raise QueueFullError(f"La cola de espera está llena ({self._max_waiting} pedidos).")

        started = time.perf_counter()
        self.waiting += 1
        try:
            async with asyncio.timeout(self._wait_timeout):
                await self._slots.acquire()
        except TimeoutError:
            raise QueueTimeoutError(f"No hubo un worker libre en {self._wait_timeout:g} s.") from None
        finally:
            self.waiting -= 1

        self.running += 1
        try:
            yield time.perf_counter() - started
        finally:
            self.running -= 1
            self._slots.release()

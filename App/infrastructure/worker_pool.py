"""Pool de procesos que separa el runtime HTTP del trabajo de CPU.

Consigna, punto 5.4: "Separar el runtime HTTP de la ejecución del algoritmo
de extracción". Extraer un PDF ocupa la CPU cientos de milisegundos. Si eso
corriera en el event loop de uvicorn, durante ese tiempo la réplica no podría
ni aceptar conexiones ni responder el health check del balanceador (que la
daría por caída). Por eso la extracción corre en procesos aparte y el event
loop solo recibe pedidos, espera resultados y responde.

Se usan procesos y no hilos porque en CPython el GIL impide que dos hilos
ejecuten código Python al mismo tiempo.
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from typing import Any

from App.domain.exceptions import WorkerCrashedError

logger = logging.getLogger(__name__)


class WorkerPool:
    def __init__(self, size: int, initializer: Callable[[], None] | None = None) -> None:
        self.size = size
        self._initializer = initializer
        self._executor = self._new_executor()
        self._warm_up_task: asyncio.Task[None] | None = None

    def _new_executor(self) -> ProcessPoolExecutor:
        # "spawn" arranca procesos limpios (sin copiar el estado del event
        # loop, como haría "fork") y funciona igual en Linux y en Windows.
        return ProcessPoolExecutor(
            max_workers=self.size,
            mp_context=multiprocessing.get_context("spawn"),
            initializer=self._initializer,
        )

    async def start(self) -> None:
        """Levanta todos los workers antes de recibir tráfico.

        ProcessPoolExecutor crea los procesos recién cuando llegan tareas. Sin
        este calentamiento, los primeros pedidos reales pagarían el arranque
        del proceso y la carga de MuPDF.
        """
        await asyncio.gather(*(self.run(_warm_up) for _ in range(self.size)))

    async def run[T](self, function: Callable[..., T], *args: Any) -> T:
        """Ejecuta ``function(*args)`` en un worker y espera el resultado.

        Raises:
            WorkerCrashedError: si el worker murió (por ejemplo, el kernel lo
                mató por exceder el límite de memoria del contenedor).
        """
        executor = self._executor
        try:
            return await asyncio.get_running_loop().run_in_executor(executor, function, *args)
        except BrokenProcessPool as error:
            # Un ProcessPoolExecutor roto no se recupera solo: todos los
            # pedidos siguientes fallarían. Lo reemplazamos por uno nuevo.
            # Si varios pedidos fallan juntos, solo el primero lo reemplaza.
            if executor is self._executor:
                logger.error("Un worker murió inesperadamente; se reinicia el pool.")
                self._executor = self._new_executor()
                executor.shutdown(wait=False, cancel_futures=True)
                # Se calienta el pool nuevo en segundo plano para que el próximo
                # pedido no pague el arranque del proceso y la carga de MuPDF.
                self._warm_up_task = asyncio.create_task(self.start())
            raise WorkerCrashedError("El proceso de extracción terminó inesperadamente.") from error

    def close(self) -> None:
        """Espera a que terminen las tareas en curso y apaga los workers."""
        self._executor.shutdown(wait=True, cancel_futures=True)


def _warm_up() -> None:
    """Tarea vacía: alcanza con que el worker arranque y corra su initializer."""

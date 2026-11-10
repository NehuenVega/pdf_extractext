"""Adaptador del puerto IMarkdownExtractor: extrae en un pool de procesos.

La conversión ocupa la CPU cientos de milisegundos por PDF; corriéndola en
procesos aparte, el event loop de uvicorn sigue libre para recibir pedidos y
contestar el health check del balanceador mientras tanto.
"""

from App.domain.models import RenderedMarkdown
from App.infrastructure.markdown.worker import extract_to_json, init_worker
from App.infrastructure.worker_pool import WorkerPool


class ProcessPoolMarkdownExtractor:
    def __init__(self, workers: int) -> None:
        self._pool = WorkerPool(size=workers, initializer=init_worker)

    async def start(self) -> None:
        await self._pool.start()

    def close(self) -> None:
        self._pool.close()

    async def extract(self, file_bytes: bytes) -> RenderedMarkdown:
        return await self._pool.run(extract_to_json, file_bytes)

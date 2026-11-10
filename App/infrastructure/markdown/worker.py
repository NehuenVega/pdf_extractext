"""Tareas que se ejecutan dentro de los procesos worker.

Este módulo es lo único que cruza la frontera entre procesos: el proceso HTTP
le pasa los bytes del PDF y recibe la respuesta ya serializada.
"""

import signal

import orjson
import pymupdf

from App.domain.models import RenderedMarkdown
from App.infrastructure.markdown import extract_markdown


def init_worker() -> None:
    """Prepara cada proceso worker al arrancar."""
    # Ctrl+C llega a todos los procesos del grupo. Lo ignoramos acá para que
    # sea el proceso principal quien apague el pool en orden.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    # MuPDF imprime en stderr cada problema que encuentra. Los que importan
    # ya llegan como excepción (y se registran en el log JSON); el resto es
    # ruido que, bajo carga, ensucia los logs.
    pymupdf.TOOLS.mupdf_display_errors(False)
    pymupdf.TOOLS.mupdf_display_warnings(False)


def extract_to_json(pdf: bytes) -> RenderedMarkdown:
    """Extrae el PDF y serializa la respuesta ``{"content", "page_count"}``.

    La serialización a JSON se hace acá, en el worker, para que el proceso
    HTTP no gaste CPU en convertir textos de cientos de KB: solo reenvía bytes.
    """
    # No vaciamos la caché de MuPDF entre documentos (store_shrink): medimos
    # que la memoria del worker queda estable en ~63 MB igual, y vaciarla
    # hacía cada extracción ~7 % más lenta.
    result = extract_markdown(pdf)
    body = orjson.dumps({"content": result.content, "page_count": result.page_count})
    return RenderedMarkdown(body=body, page_count=result.page_count)

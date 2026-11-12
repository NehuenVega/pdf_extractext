"""Caso de uso de POST /extract: convertir un PDF a Markdown.

Es el endpoint que se somete a las pruebas de carga, así que a diferencia de
/extract-text no pasa por MongoDB: siempre extrae. Antes de ocupar un worker
pide lugar al control de admisión, que rechaza con 503 cuando la réplica ya
tiene más trabajo del que puede terminar a tiempo (backpressure).
"""

import time
from dataclasses import dataclass

from App.domain.exceptions import InvalidPdfError
from App.domain.interfaces import IMarkdownExtractor
from App.services.admission import AdmissionController

# Según la especificación de PDF, la firma "%PDF-" debe estar al principio,
# pero los lectores la aceptan dentro del primer KB (algunos generadores
# agregan basura antes). Hacemos lo mismo.
PDF_SIGNATURE = b"%PDF-"
PDF_SIGNATURE_SEARCH_BYTES = 1024


@dataclass(frozen=True, slots=True)
class MarkdownResult:
    body: bytes  # JSON {"content", "page_count"} listo para enviar
    page_count: int
    queue_seconds: float
    extract_seconds: float


class MarkdownExtractionService:
    def __init__(self, extractor: IMarkdownExtractor, admission: AdmissionController) -> None:
        self.extractor = extractor
        self.admission = admission

    async def extract(self, pdf: bytes) -> MarkdownResult:
        """Convierte el PDF a Markdown.

        Raises:
            InvalidPdfError: si el archivo no tiene la firma de un PDF.
            UnreadablePdfError: si es un PDF dañado o con contraseña.
            ServiceOverloadedError: si no hay lugar en la cola de la réplica.
        """
        # Se valida antes de entrar a la cola: un archivo que no es PDF no
        # tiene por qué esperar ni ocupar un worker.
        if PDF_SIGNATURE not in pdf[:PDF_SIGNATURE_SEARCH_BYTES]:
            raise InvalidPdfError("El archivo no es un PDF (no tiene la firma %PDF-).")

        async with self.admission.slot() as queue_seconds:
            started = time.perf_counter()
            rendered = await self.extractor.extract(pdf)
            extract_seconds = time.perf_counter() - started

        return MarkdownResult(rendered.body, rendered.page_count, queue_seconds, extract_seconds)

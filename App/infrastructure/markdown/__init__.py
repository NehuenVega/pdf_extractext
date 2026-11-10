"""Conversión de PDF a Markdown (la usa POST /extract).

Se divide en dos pasos con responsabilidades separadas:
``reader`` (PDF → líneas con estilo, usa MuPDF) y
``converter`` (líneas con estilo → Markdown, lógica pura).
"""

from dataclasses import dataclass

from App.infrastructure.markdown.converter import to_markdown
from App.infrastructure.markdown.reader import read_pdf


@dataclass(frozen=True, slots=True)
class Extraction:
    content: str
    page_count: int


def extract_markdown(pdf: bytes) -> Extraction:
    """Extrae el texto del PDF en formato Markdown.

    Raises:
        UnreadablePdfError: si el archivo no es un PDF legible.
    """
    text = read_pdf(pdf)
    return Extraction(content=to_markdown(text.blocks), page_count=text.page_count)

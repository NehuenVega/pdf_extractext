"""Fixtures compartidas: PDFs generados en memoria para los tests.

No usan los PDFs de tests/stress/pdfs a propósito: pesan varios MB y los
tests tienen que correr en segundos y no depender de qué archivos haya ahí.
"""

from collections.abc import Callable

import pymupdf
import pytest

BuildPdf = Callable[..., bytes]


@pytest.fixture(scope="session")
def build_pdf() -> BuildPdf:
    """Devuelve una función que arma un PDF con líneas (texto, tamaño)."""

    def build(*lines: tuple[str, float], pages: int = 1) -> bytes:
        document = pymupdf.open()
        for _ in range(pages):
            document.new_page()
        y = 72
        for text, size in lines:
            document[0].insert_text((72, y), text, fontsize=size)
            y += size * 2
        return document.tobytes()

    return build


@pytest.fixture(scope="session")
def long_pdf() -> bytes:
    """PDF de 150 páginas llenas de texto: tarda lo suficiente en procesarse
    como para que dos pedidos simultáneos se superpongan."""
    document = pymupdf.open()
    for number in range(150):
        page = document.new_page()
        page.insert_text((72, 60), f"Capítulo {number + 1}", fontsize=20)
        for row in range(45):
            page.insert_text((72, 100 + row * 15), f"Línea {row} del capítulo con texto de relleno para extraer.")
    return document.tobytes()

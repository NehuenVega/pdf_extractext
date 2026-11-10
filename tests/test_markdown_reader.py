"""Tests de la lectura de PDFs con MuPDF (PDFs chicos creados en memoria)."""

import pymupdf
import pytest

from App.domain.exceptions import UnreadablePdfError
from App.infrastructure.markdown import extract_markdown
from App.infrastructure.markdown.reader import read_pdf


def make_pdf(*lines: tuple[str, float], pages: int = 1) -> bytes:
    """Arma un PDF con las líneas (texto, tamaño) en la primera página."""
    document = pymupdf.open()
    for _ in range(pages):
        document.new_page()
    y = 72
    for text, size in lines:
        document[0].insert_text((72, y), text, fontsize=size)
        y += size * 2
    return document.tobytes()


def test_reads_text_and_font_size_of_each_line():
    pdf = make_pdf(("Título grande", 24), ("Texto normal", 11))

    lines = [line for block in read_pdf(pdf).blocks for line in block]

    assert [(line.text, line.size) for line in lines] == [("Título grande", 24), ("Texto normal", 11)]


def test_counts_all_pages_including_empty_ones():
    pdf = make_pdf(("Solo la primera página tiene texto", 11), pages=3)

    assert read_pdf(pdf).page_count == 3


def test_detects_bold_fonts():
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "En negrita", fontname="hebo")  # Helvetica-Bold

    (block,) = read_pdf(document.tobytes()).blocks

    assert block[0].bold


def test_garbage_bytes_raise_unreadable_pdf_error():
    with pytest.raises(UnreadablePdfError):
        read_pdf(b"%PDF-1.7 esto no es un PDF de verdad")


def test_password_protected_pdf_raises_unreadable_pdf_error():
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "Secreto")
    encrypted = document.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="clave", owner_pw="clave")

    with pytest.raises(UnreadablePdfError, match="contraseña"):
        read_pdf(encrypted)


def test_extract_markdown_returns_content_and_page_count():
    pdf = make_pdf(("Informe", 24), ("Este es el cuerpo del informe con bastante texto.", 11), pages=2)

    result = extract_markdown(pdf)

    assert result.content == "# Informe\n\nEste es el cuerpo del informe con bastante texto."
    assert result.page_count == 2

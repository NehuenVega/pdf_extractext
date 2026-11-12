import pymupdf
import pytest

from App.domain.exceptions import UnreadablePdfError
from App.infrastructure.pymupdf_extractor import PyMuPdfExtractor


def build_pdf(*page_texts: str) -> bytes:
    document = pymupdf.open()
    for text in page_texts:
        document.new_page().insert_text((72, 72), text)
    return document.tobytes()


def test_extrae_el_texto_de_cada_pagina():
    pages = PyMuPdfExtractor().extract_text(build_pdf("Primera página", "Segunda página"))

    assert [page.page_number for page in pages] == [1, 2]
    assert pages[0].content.strip() == "Primera página"
    assert pages[1].content.strip() == "Segunda página"


@pytest.mark.parametrize("data", [b"", b"esto no es un PDF", b"%PDF-1.7 contenido roto"])
def test_pdf_ilegible_lanza_error_de_dominio(data):
    with pytest.raises(UnreadablePdfError):
        PyMuPdfExtractor().extract_text(data)


def test_pdf_con_contrasena_lanza_error_de_dominio():
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "Secreto")
    protected = document.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="clave", owner_pw="clave")

    with pytest.raises(UnreadablePdfError, match="contraseña"):
        PyMuPdfExtractor().extract_text(protected)

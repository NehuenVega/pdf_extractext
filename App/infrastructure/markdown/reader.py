"""Lectura de PDFs con MuPDF: de bytes a líneas de texto con su estilo.

Es el único módulo del proyecto que conoce MuPDF. Usa los bindings oficiales
de MuPDF que vienen dentro de PyMuPDF (``pymupdf.mupdf``) porque necesitamos
dos cosas que la API de alto nivel no da juntas:

1. Abrir el PDF directamente sobre los bytes recibidos, sin copiarlos
   (``fz_open_memory``), como pide la consigna: "sin volcar todo el archivo a
   disco ni duplicar buffers en memoria".
2. Obtener por cada línea su texto, tamaño de letra y si es negrita en una
   sola pasada hecha en C (``fz_print_stext_page_as_json``). Medimos que
   cuesta lo mismo que extraer texto plano y bastante menos que
   ``page.get_text("dict")`` (ver docs/adr/0001-motor-de-extraccion.md).

Referencias (MuPDF 1.28):
- fz_open_memory: https://mupdf.readthedocs.io/en/1.28.0/_static/generated/c/html/stream_8h.html#a015e7cf420618fd4dd8e33e136ad2620
- fz_print_stext_page_as_json: https://mupdf.readthedocs.io/en/1.28.0/_static/generated/c/html/structured-text_8h.html#aa432dede23b0972f6cb72ceaf440f86c
- python_buffer_data / fz_buffer_storage_memoryview: https://mupdf.readthedocs.io/en/1.28.0/reference/cxx-and-derived-bindings.html
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import orjson
from pymupdf import mupdf

from App.domain.exceptions import UnreadablePdfError

# Opciones de extracción de MuPDF:
# - MEDIABOX_CLIP: ignora texto que cae fuera de la página visible.
# - DEHYPHENATE: une las palabras cortadas con guion al final de una línea.
# No pedimos imágenes (no sirven para Markdown de texto y decodificarlas es
# caro) y no preservamos ligaduras, así "ﬁ" sale como "fi".
_STEXT_FLAGS = mupdf.FZ_STEXT_MEDIABOX_CLIP | mupdf.FZ_STEXT_DEHYPHENATE

# Tamaño inicial del buffer donde MuPDF escribe el JSON de cada página.
# Crece solo si hace falta; 64 KB alcanza para una página de texto típica.
_INITIAL_JSON_BUFFER_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class TextLine:
    """Una línea de texto tal como la ve MuPDF, con su estilo."""

    text: str
    size: float
    bold: bool


# Un bloque es un grupo de líneas que MuPDF considera visualmente juntas
# (normalmente un párrafo, un título o un ítem de lista).
Block = tuple[TextLine, ...]


@dataclass(frozen=True, slots=True)
class PdfText:
    """Texto de todo el documento, en orden de lectura."""

    blocks: tuple[Block, ...]
    page_count: int


def read_pdf(pdf: bytes) -> PdfText:
    """Lee el PDF y devuelve sus bloques de texto con estilo.

    Raises:
        UnreadablePdfError: si el PDF está dañado o protegido con contraseña.
    """
    try:
        # fz_open_memory NO toma posesión de los datos: los bytes de `pdf`
        # tienen que seguir vivos mientras se usa el documento. Como `pdf` es
        # un parámetro de esta función, lo están hasta que ella termina.
        stream = mupdf.fz_open_memory(mupdf.python_buffer_data(pdf), len(pdf))
        document = mupdf.fz_open_document_with_stream("application/pdf", stream)
        if mupdf.fz_needs_password(document):
            raise UnreadablePdfError("El PDF está protegido con contraseña.")

        page_count = mupdf.fz_count_pages(document)
        blocks = tuple(block for number in range(page_count) for block in _read_page(document, number))
    except (mupdf.FzErrorBase, ValueError, KeyError) as error:
        # FzErrorBase: MuPDF no pudo leer el archivo. ValueError/KeyError: el
        # JSON de una página vino con una forma inesperada (por las dudas: el
        # contenido sale de un archivo que no controlamos). El detalle queda en
        # la causa de la excepción; al cliente le llega un mensaje genérico.
        raise UnreadablePdfError("El PDF está dañado o no se puede leer.") from error

    return PdfText(blocks=blocks, page_count=page_count)


def _read_page(document: mupdf.FzDocument, number: int) -> list[Block]:
    options = mupdf.FzStextOptions()
    options.flags = _STEXT_FLAGS
    text_page = mupdf.FzStextPage(mupdf.fz_load_page(document, number), options)

    buffer = mupdf.fz_new_buffer(_INITIAL_JSON_BUFFER_BYTES)
    output = mupdf.FzOutput(buffer)
    mupdf.fz_print_stext_page_as_json(output, text_page, 1.0)
    output.fz_close_output()

    # orjson lee directo de la memoria del buffer de MuPDF: no hace falta
    # copiar el JSON a un objeto bytes intermedio.
    page = orjson.loads(mupdf.fz_buffer_storage_memoryview(buffer))
    return [block for raw_block in page["blocks"] if (block := _parse_block(raw_block))]


def _parse_block(raw_block: dict[str, Any]) -> Block:
    if raw_block.get("type") != "text":
        return ()
    return tuple(
        TextLine(
            text=line["text"],
            size=float(line["font"]["size"]),
            bold=line["font"]["weight"] == "bold",
        )
        for line in raw_block["lines"]
        if line["text"].strip()
    )

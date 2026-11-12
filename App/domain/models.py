from pydantic import BaseModel
from typing import List, NamedTuple

class ExtractedPage(BaseModel):
    page_number: int
    content: str

class PdfExtractionResponse(BaseModel):
    filename: str
    total_pages: int
    pages: List[ExtractedPage]

# Respuesta de POST /extract (la usa la documentación de /docs).
class MarkdownExtractionResponse(BaseModel):
    content: str
    page_count: int

# Lo que devuelve un worker de extracción: la respuesta ya serializada a
# JSON, para que el proceso HTTP no gaste CPU en convertirla.
class RenderedMarkdown(NamedTuple):
    body: bytes
    page_count: int

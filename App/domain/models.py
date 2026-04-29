from pydantic import BaseModel
from typing import List

class ExtractedPage(BaseModel):
    page_number: int
    content: str

class PdfExtractionResponse(BaseModel):
    filename: str
    total_pages: int
    pages: List[ExtractedPage]

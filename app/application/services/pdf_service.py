"""PDF text extraction service."""

import io
from dataclasses import dataclass
from pypdf import PdfReader


@dataclass
class ExtractedPDF:
    filename: str
    text: str
    page_count: int
    character_count: int


class PDFService:
    def extract_text(self, file_content: bytes, filename: str) -> ExtractedPDF:
        reader = PdfReader(io.BytesIO(file_content))
        text_parts = []

        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

        full_text = "\n\n".join(text_parts)

        return ExtractedPDF(
            filename=filename,
            text=full_text,
            page_count=len(reader.pages),
            character_count=len(full_text),
        )

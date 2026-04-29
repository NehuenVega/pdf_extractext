import fitz
from typing import List
from App.domain.interfaces import IPdfExtractor
from App.domain.models import ExtractedPage

class PyMuPdfExtractor(IPdfExtractor):
    def extract_text(self, file_bytes: bytes) -> List[ExtractedPage]:
        extracted_pages = []
        # Abrimos el PDF desde el stream de bytes
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for page_num, page in enumerate(doc, start=1):
                text = page.get_text()
                extracted_pages.append(
                    ExtractedPage(page_number=page_num, content=text)
                )
        return extracted_pages 

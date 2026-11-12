import pymupdf
from typing import List
from App.domain.exceptions import UnreadablePdfError
from App.domain.interfaces import IPdfExtractor
from App.domain.models import ExtractedPage

class PyMuPdfExtractor(IPdfExtractor):
    def extract_text(self, file_bytes: bytes) -> List[ExtractedPage]:
        extracted_pages = []
        try:
            # Abrimos el PDF desde el stream de bytes
            with pymupdf.open(stream=file_bytes, filetype="pdf") as doc:
                if doc.needs_pass:
                    raise UnreadablePdfError("El PDF está protegido con contraseña.")
                for page_num, page in enumerate(doc, start=1):
                    text = page.get_text()
                    extracted_pages.append(
                        ExtractedPage(page_number=page_num, content=text)
                    )
        except pymupdf.FileDataError as error:
            raise UnreadablePdfError("El PDF está dañado o no se puede leer.") from error
        return extracted_pages

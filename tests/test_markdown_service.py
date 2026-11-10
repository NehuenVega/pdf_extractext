"""Tests del caso de uso de POST /extract con un extractor falso (sin procesos)."""

import pytest

from App.domain.exceptions import InvalidPdfError, QueueFullError
from App.domain.interfaces import IMarkdownExtractor
from App.domain.models import RenderedMarkdown
from App.services.admission import AdmissionController
from App.services.markdown_service import MarkdownExtractionService


class FakeMarkdownExtractor(IMarkdownExtractor):
    def __init__(self):
        self.received = []

    async def extract(self, file_bytes: bytes) -> RenderedMarkdown:
        self.received.append(file_bytes)
        return RenderedMarkdown(body=b'{"content": "# Hola", "page_count": 1}', page_count=1)


def build_service(extractor, max_waiting=8):
    admission = AdmissionController(max_concurrent=1, max_waiting=max_waiting, wait_timeout=1)
    return MarkdownExtractionService(extractor, admission)


async def test_returns_the_rendered_body_and_timings():
    extractor = FakeMarkdownExtractor()

    result = await build_service(extractor).extract(b"%PDF-1.7 ...")

    assert result.body == b'{"content": "# Hola", "page_count": 1}'
    assert result.page_count == 1
    assert result.queue_seconds >= 0 and result.extract_seconds >= 0
    assert extractor.received == [b"%PDF-1.7 ..."]


async def test_accepts_the_signature_within_the_first_kilobyte():
    result = await build_service(FakeMarkdownExtractor()).extract(b" " * 500 + b"%PDF-1.7")

    assert result.page_count == 1


@pytest.mark.parametrize("data", [b"", b"no es un PDF", b" " * 1024 + b"%PDF-1.7"])
async def test_rejects_files_without_pdf_signature_before_queueing(data):
    extractor = FakeMarkdownExtractor()

    with pytest.raises(InvalidPdfError):
        await build_service(extractor).extract(data)
    assert extractor.received == []


async def test_full_queue_is_reported_as_overloaded():
    service = build_service(FakeMarkdownExtractor(), max_waiting=0)

    async with service.admission.slot():  # ocupa el único worker
        with pytest.raises(QueueFullError):
            await service.extract(b"%PDF-1.7")

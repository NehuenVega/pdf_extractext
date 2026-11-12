"""Tests de la lectura del body: tiempo límite y cliente que se desconecta.

Se arma un pedido ASGI a mano, con una función ``receive`` que simula al
cliente: así se pueden reproducir un envío lento y un corte de conexión sin
red de verdad.
"""

import asyncio

import pytest
from fastapi import HTTPException, Request

from App.api.uploads import read_pdf_upload
from App.domain.exceptions import FileTooLargeError

PDF = b"%PDF-1.7 contenido"


def request_with(messages: list[dict], delay_seconds: float = 0.0) -> Request:
    """Pedido cuyo cliente envía ``messages`` esperando ``delay_seconds`` antes de cada uno."""
    pending = list(messages)

    async def receive() -> dict:
        await asyncio.sleep(delay_seconds)
        return pending.pop(0)

    scope = {"type": "http", "method": "POST", "path": "/extract", "headers": []}
    return Request(scope, receive)


def read(request: Request, timeout_seconds: float = 5.0) -> bytes:
    return asyncio.run(read_pdf_upload(request, max_bytes=1024, timeout_seconds=timeout_seconds))


def test_body_sent_in_several_chunks_is_joined():
    request = request_with(
        [
            {"type": "http.request", "body": PDF[:5], "more_body": True},
            {"type": "http.request", "body": PDF[5:], "more_body": False},
        ]
    )

    assert read(request) == PDF


def test_body_that_arrives_too_slowly_is_rejected_with_408():
    request = request_with([{"type": "http.request", "body": PDF, "more_body": False}], delay_seconds=0.5)

    with pytest.raises(HTTPException) as error:
        read(request, timeout_seconds=0.05)

    assert error.value.status_code == 408


def test_client_that_disconnects_mid_upload_is_reported_as_499():
    request = request_with(
        [
            {"type": "http.request", "body": PDF[:5], "more_body": True},
            {"type": "http.disconnect"},
        ]
    )

    with pytest.raises(HTTPException) as error:
        read(request)

    assert error.value.status_code == 499


def test_body_larger_than_the_limit_is_rejected_while_reading():
    request = request_with(
        [
            {"type": "http.request", "body": b"%PDF-" + b"0" * 1000, "more_body": True},
            {"type": "http.request", "body": b"0" * 1000, "more_body": False},
        ]
    )

    with pytest.raises(FileTooLargeError):
        read(request)

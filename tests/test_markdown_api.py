"""Tests de POST /extract de punta a punta: HTTP + control de admisión + pool de procesos real."""

import asyncio
import logging

import httpx
import pytest
from fastapi.testclient import TestClient

from App.core.config import Settings
from App.main import create_app

REPORT = (("Informe de carga", 22), ("Resultados de la prueba con texto de cuerpo suficiente.", 11))


@pytest.fixture(scope="module")
def client():
    # Un solo servicio (con sus procesos worker) para todo el módulo: levantar
    # workers lleva alrededor de un segundo y no hace falta repetirlo.
    with TestClient(create_app(Settings(MAX_FILE_SIZE_MB=1))) as test_client:
        yield test_client


def test_binary_upload_returns_markdown_and_page_count(client, build_pdf):
    response = client.post("/extract", content=build_pdf(*REPORT, pages=3), headers={"Content-Type": "application/pdf"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {
        "content": "# Informe de carga\n\nResultados de la prueba con texto de cuerpo suficiente.",
        "page_count": 3,
    }


def test_multipart_upload_gives_the_same_result_as_binary(client, build_pdf):
    pdf = build_pdf(*REPORT)

    binary = client.post("/extract", content=pdf, headers={"Content-Type": "application/pdf"})
    multipart = client.post("/extract", files={"file": ("informe.pdf", pdf, "application/pdf")})

    assert multipart.status_code == 200
    assert multipart.json() == binary.json()


def test_upload_without_content_type_is_treated_as_binary(client, build_pdf):
    response = client.post("/extract", content=build_pdf(*REPORT))

    assert response.status_code == 200


def test_any_non_multipart_content_type_is_treated_as_binary(client, build_pdf):
    # Es lo que manda "curl --data-binary @archivo.pdf" si no se agrega -H.
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = client.post("/extract", content=build_pdf(*REPORT), headers=headers)

    assert response.status_code == 200


def test_extract_does_not_use_the_mongo_cache(client, build_pdf):
    # El mismo PDF dos veces: las dos se extraen (tiempo de extracción > 0).
    pdf = build_pdf(*REPORT)

    for _ in range(2):
        response = client.post("/extract", content=pdf)
        assert "extract;dur=" in response.headers["server-timing"]


def test_response_reports_queue_and_extraction_time(client, build_pdf):
    response = client.post("/extract", content=build_pdf(*REPORT))

    assert response.headers["server-timing"].startswith("queue;dur=")


@pytest.mark.parametrize(
    ("body", "content_type", "status"),
    [
        pytest.param(b"", "application/pdf", 400, id="vacio"),
        pytest.param(b'{"pdf": "no"}', "application/json", 400, id="json"),
        pytest.param(b"esto no es un PDF", "application/pdf", 400, id="sin-firma"),
        pytest.param(b"%PDF-1.7 contenido roto", "application/pdf", 422, id="pdf-roto"),
        pytest.param(b"%PDF-" + b"0" * (2 * 1024 * 1024), "application/pdf", 413, id="2MB"),
    ],
)
def test_invalid_requests_get_a_json_error(client, body, content_type, status):
    response = client.post("/extract", content=body, headers={"Content-Type": content_type})

    assert response.status_code == status
    assert isinstance(response.json()["detail"], str)


def test_wrong_method_also_gets_a_json_error(client):
    response = client.get("/extract")

    assert response.status_code == 405
    assert "detail" in response.json()
    assert response.headers["allow"] == "POST"


def test_health_reports_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "running": 0, "waiting": 0}


def test_each_request_is_logged_with_its_extraction_data(client, build_pdf, caplog):
    with caplog.at_level(logging.INFO, logger="App.access"):
        client.post("/extract", content=build_pdf(*REPORT, pages=2))

    (record,) = [r for r in caplog.records if r.name == "App.access"]
    assert record.fields["status"] == 200
    assert record.fields["page_count"] == 2
    assert {"queue_ms", "extract_ms", "duration_ms"} <= record.fields.keys()


def test_overloaded_service_answers_503_instead_of_queueing(long_pdf):
    """Con 1 worker y cola 0, de dos pedidos simultáneos uno se procesa y
    el otro se rechaza en el momento con 503 + Retry-After."""
    app = create_app(Settings(EXTRACTION_WORKERS=1, MAX_QUEUE_SIZE=0))

    async def two_simultaneous_requests():
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=60) as http:
                return await asyncio.gather(
                    http.post("/extract", content=long_pdf),
                    http.post("/extract", content=long_pdf),
                )

    responses = asyncio.run(two_simultaneous_requests())

    assert sorted(response.status_code for response in responses) == [200, 503]
    rejected = next(response for response in responses if response.status_code == 503)
    assert rejected.headers["retry-after"] == "2"
    assert "cola" in rejected.json()["detail"]

from fastapi.testclient import TestClient

from App.main import create_app


def test_docs_page_has_the_custom_header_and_theme():
    response = TestClient(create_app()).get("/docs")

    assert response.status_code == 200
    assert 'class="pt-header"' in response.text
    assert "--pt-navy" in response.text
    assert 'id="swagger-ui"' in response.text


def test_every_endpoint_is_in_exactly_one_documented_section():
    schema = create_app().openapi()
    sections = {tag["name"] for tag in schema["tags"]}

    for operations in schema["paths"].values():
        for operation in operations.values():
            assert len(operation["tags"]) == 1
            assert operation["tags"][0] in sections
            assert operation["summary"]


def test_docs_texts_are_in_spanish():
    client = TestClient(create_app())

    assert '<html lang="es">' in client.get("/docs").text
    responses = client.get("/openapi.json").json()["paths"]["/api/v1/extract-text"]["post"]["responses"]
    assert responses["200"]["description"] == "Respuesta correcta"
    assert responses["422"]["description"] == "Error de validación"


def test_default_http_errors_are_in_spanish():
    client = TestClient(create_app())

    assert client.get("/no-existe").json() == {"detail": "No encontrado."}
    response = client.get("/extract")
    assert response.json() == {"detail": "Método no permitido."}
    assert response.headers["allow"] == "POST"

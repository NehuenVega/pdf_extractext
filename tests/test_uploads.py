"""Tests del parseo del Content-Type y del body multipart."""

import pytest

from fastapi import HTTPException

from App.api.uploads import extract_multipart_file, parse_content_type

PDF = b"%PDF-1.7\n...contenido binario\r\ncon saltos de linea\r\n...%%EOF"


def multipart(*parts: tuple[str, bytes], boundary: str = "limite123") -> bytes:
    """Arma un body multipart; cada parte es (encabezados, contenido)."""
    body = b""
    for headers, content in parts:
        body += f"--{boundary}\r\n{headers}\r\n\r\n".encode() + content + b"\r\n"
    return body + f"--{boundary}--\r\n".encode()


def test_parse_content_type_separates_media_type_and_parameters():
    assert parse_content_type('multipart/form-data; boundary="abc"') == ("multipart/form-data", {"boundary": "abc"})


def test_parse_content_type_normalizes_case_and_spaces():
    assert parse_content_type(" Application/PDF ") == ("application/pdf", {})


def test_file_part_is_extracted_byte_for_byte():
    body = multipart(('Content-Disposition: form-data; name="file"; filename="a.pdf"', PDF))

    assert extract_multipart_file(body, "limite123") == PDF


def test_any_field_name_is_accepted():
    body = multipart(('Content-Disposition: form-data; name="documento"; filename="x.pdf"', PDF))

    assert extract_multipart_file(body, "limite123") == PDF


def test_the_part_with_a_filename_wins_over_plain_fields():
    body = multipart(
        ('Content-Disposition: form-data; name="descripcion"', b"un campo de texto"),
        ('Content-Disposition: form-data; name="file"; filename="a.pdf"', PDF),
    )

    assert extract_multipart_file(body, "limite123") == PDF


def test_filename_only_counts_inside_content_disposition():
    body = multipart(
        ('Content-Disposition: form-data; name="pdf"\r\nX-Extra: filename=engañoso', PDF),
        ('Content-Disposition: form-data; name="nota"', b"otro campo"),
    )

    assert extract_multipart_file(body, "limite123") == PDF


def test_without_filenames_the_first_part_is_used():
    body = multipart(('Content-Disposition: form-data; name="pdf"', PDF))

    assert extract_multipart_file(body, "limite123") == PDF


@pytest.mark.parametrize(
    ("body", "boundary"),
    [
        (b"--limite123\r\nsin fin de encabezados", "limite123"),
        (b"--limite123\r\nContent-Disposition: form-data\r\n\r\nsin cierre", "limite123"),
        (b"no hay separadores", "limite123"),
        (b"--limite123--\r\n", "limite123"),
        (b"--limite123\r\n...", ""),
    ],
)
def test_malformed_bodies_are_rejected_with_400(body, boundary):
    with pytest.raises(HTTPException) as error:
        extract_multipart_file(body, boundary)

    assert error.value.status_code == 400

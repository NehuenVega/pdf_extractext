"""Lectura del PDF que llega en el pedido HTTP.

La consigna permite dos formas de enviar el archivo y aceptamos las dos:

- **multipart/form-data:** el PDF viaja como una parte del formulario. Se
  acepta cualquier nombre de campo; se toma la primera parte que declara un
  archivo (``filename`` en Content-Disposition) o, si ninguna lo hace, la
  primera parte.
- **Binario directo:** cualquier otro Content-Type (o ninguno). No exigimos
  ``application/pdf`` porque muchos clientes mandan otra cosa; por ejemplo,
  ``curl --data-binary`` sin ``-H`` usa ``application/x-www-form-urlencoded``.
  Lo que decide si el archivo es un PDF es su firma ``%PDF-`` (lo valida
  MarkdownExtractionService).

¿Por qué no usamos ``UploadFile`` de FastAPI? Porque el parser de formularios
de Starlette guarda los archivos de más de 1 MB en un archivo temporal en disco, y la consigna pide
explícitamente no volcar el archivo a disco. El body ya está en memoria, así
que alcanza con ubicar los separadores con ``bytes.find`` (implementado en C)
y recortar la parte del archivo.
"""

from __future__ import annotations

import asyncio

from fastapi import HTTPException, Request
from starlette.requests import ClientDisconnect

from App.domain.exceptions import FileTooLargeError

async def read_pdf_upload(request: Request, max_bytes: int, timeout_seconds: float) -> bytes:
    """Devuelve los bytes del archivo enviado en el pedido.

    Raises:
        FileTooLargeError: si supera ``max_bytes``.
        HTTPException: si el pedido está vacío, tarda demasiado en llegar o el
            multipart está mal formado.
    """
    media_type, parameters = parse_content_type(request.headers.get("content-type", ""))
    body = await _read_body(request, max_bytes, timeout_seconds)
    if not body:
        raise HTTPException(400, "El pedido no trae ningún archivo.")

    if media_type == "multipart/form-data":
        return extract_multipart_file(body, parameters.get("boundary", ""))
    return body


async def _read_body(request: Request, max_bytes: int, timeout_seconds: float) -> bytes:
    """Lee el body cortando apenas supera el máximo permitido o el tiempo límite.

    Primero mira Content-Length para rechazar sin leer nada; igual cuenta lo
    que va llegando, porque ese encabezado puede faltar (envío chunked).

    El tiempo límite protege a la réplica de un cliente que manda el archivo de
    a gotas: como procesa un pedido por vez, la dejaría bloqueada. (El
    ``timeout http-request`` de HAProxy solo cubre los encabezados.)
    """
    declared = request.headers.get("content-length", "")
    if declared.isascii() and declared.isdigit() and int(declared) > max_bytes:
        raise _too_large(max_bytes)

    chunks: list[bytes] = []
    received = 0
    try:
        async with asyncio.timeout(timeout_seconds):
            async for chunk in request.stream():
                received += len(chunk)
                if received > max_bytes:
                    raise _too_large(max_bytes)
                chunks.append(chunk)
    except TimeoutError:
        raise HTTPException(408, f"El archivo no terminó de llegar en {timeout_seconds:g} s.") from None
    except ClientDisconnect:
        # El cliente cortó a mitad del envío (por ejemplo, venció su timeout).
        # Nadie va a recibir la respuesta: 499 solo queda en el log de acceso.
        raise HTTPException(499, "El cliente cerró la conexión antes de enviar el archivo.") from None
    return b"".join(chunks)


def _too_large(max_bytes: int) -> FileTooLargeError:
    return FileTooLargeError(f"El archivo supera el límite de {max_bytes // (1024 * 1024)} MB.")


def parse_content_type(header: str) -> tuple[str, dict[str, str]]:
    """Separa ``multipart/form-data; boundary=abc`` en tipo y parámetros."""
    media_type, *raw_parameters = header.split(";")
    parameters = {}
    for raw in raw_parameters:
        name, _, value = raw.strip().partition("=")
        parameters[name.lower()] = value.strip().strip('"')
    return media_type.strip().lower(), parameters


def extract_multipart_file(body: bytes, boundary: str) -> bytes:
    """Devuelve el contenido del archivo enviado en un body multipart.

    Formato (RFC 7578)::

        --BOUNDARY\\r\\n
        Content-Disposition: form-data; name="file"; filename="a.pdf"\\r\\n
        \\r\\n
        <bytes del archivo>\\r\\n
        --BOUNDARY--\\r\\n

    Raises:
        HTTPException: si el body no respeta el formato o no trae ninguna parte.
    """
    if not boundary:
        raise _invalid_multipart("falta el parámetro boundary en el Content-Type")

    delimiter = b"--" + boundary.encode("latin-1")
    position = body.find(delimiter)
    if position < 0:
        raise _invalid_multipart("no se encontró el separador de partes")

    first_part: tuple[int, int] | None = None
    while True:
        part_start = position + len(delimiter)
        if body.startswith(b"--", part_start):  # "--BOUNDARY--" cierra el body
            break
        headers_end = body.find(b"\r\n\r\n", part_start)
        if headers_end < 0:
            raise _invalid_multipart("una parte no tiene fin de encabezados")
        content_start = headers_end + 4
        next_delimiter = body.find(b"\r\n" + delimiter, content_start)
        if next_delimiter < 0:
            raise _invalid_multipart("una parte no tiene separador de cierre")

        content = (content_start, next_delimiter)
        if _declares_file(body[part_start:headers_end]):
            return body[content[0] : content[1]]
        first_part = first_part or content
        position = next_delimiter + 2  # saltea el "\r\n" previo al separador

    if first_part is None:
        raise _invalid_multipart("no trae ninguna parte")
    return body[first_part[0] : first_part[1]]


def _declares_file(part_headers: bytes) -> bool:
    """True si el Content-Disposition de la parte trae ``filename``."""
    for line in part_headers.lower().split(b"\r\n"):
        if line.startswith(b"content-disposition:") and b"filename" in line:
            return True
    return False


def _invalid_multipart(reason: str) -> HTTPException:
    return HTTPException(400, f"multipart/form-data inválido: {reason}.")

# ADR-0004: Python 3.13 + Starlette + Uvicorn

## Estado
Reemplazado en parte por [ADR-0006](0006-fastapi-al-integrar-los-proyectos.md):
al integrar el microservicio en PDFtrack se usa FastAPI en lugar de Starlette.
Python 3.13, uvicorn y orjson siguen vigentes.

## Fecha
2026-10-07

## Contexto

La consigna da libertad de stack. Como el trabajo pesado lo hace MuPDF (en C),
el lenguaje del servicio importa sobre todo por tres cosas: qué tan fácil es
usar MuPDF, cuánto cuesta el manejo HTTP de cada pedido y qué tan legible le
queda el código a todo el equipo.

## Decisión

- **Python 3.13**: PyMuPDF trae los bindings oficiales de MuPDF listos para
  usar y es el lenguaje que maneja todo el equipo.
- **Starlette** (framework ASGI mínimo) en lugar de FastAPI: el endpoint recibe
  un cuerpo binario o multipart y lo procesamos a mano, así que la validación
  automática de FastAPI no aporta. Además, el parser de formularios de
  Starlette/FastAPI guarda en disco los archivos de más de 1 MB, algo que la
  consigna pide evitar.
- **Uvicorn** con `httptools` y `uvloop` (parsers y event loop en C en Linux).
- **orjson** para el JSON de respuesta (rápido con textos grandes).

## Alternativas consideradas

### Go con bindings de MuPDF (go-fitz)
- A favor: binario chico, manejo HTTP muy eficiente.
- En contra: el costo dominante es MuPDF, que es el mismo en ambos lenguajes.
  El manejo HTTP de Python es una fracción mínima del tiempo por pedido (se ve
  en el log: `duration_ms` contra `extract_ms`). El equipo conoce menos Go.
- Rechazada.

### Node.js con pdf.js
- En contra: pdf.js es bastante más lento que MuPDF para extraer texto.
- Rechazada.

### FastAPI
- En contra: ver arriba (subida a disco y validación que no usamos).
- Rechazada.

## Consecuencias

- Hay que usar procesos para el paralelismo (GIL): ver ADR-0003.
- Dependencias mínimas y fijadas en `requirements.txt`.

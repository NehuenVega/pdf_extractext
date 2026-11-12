# ADR-0001: Motor de extracción — MuPDF + conversor propio a Markdown

## Estado
Aceptado

## Fecha
2026-10-07

## Contexto

El endpoint `POST /extract` tiene que devolver el contenido del PDF **en
Markdown**. La extracción es lo único que consume CPU en el servicio, así que
su costo por documento define la capacidad de cada réplica (1 CPU) y, por lo
tanto, el throughput de todo el sistema. La consigna sugiere "librerías de bajo
consumo de CPU y memoria que lean el stream sin volcar todo el archivo a disco
ni duplicar buffers en memoria".

Medimos 8 alternativas sobre los 4 PDFs sustitutos (informe §6.4), cada una en un proceso
nuevo y tomando la mediana de 5 corridas (`scripts/benchmark_extractors.py`,
datos en `docs/investigacion/benchmark_extraccion.json`):

| Motor | 292 pág. | 9,6 MB con gráficos | Total 4 PDFs | Pico de memoria |
|---|---:|---:|---:|---:|
| PyMuPDF `get_text` (solo texto) | 429 ms | 209 ms | 679 ms | 65 MB |
| **Nuestro extractor (Markdown)** | **464 ms** | **199 ms** | **704 ms** | **65 MB** |
| PyMuPDF `get_text("dict")` (texto + tamaños) | 640 ms | 219 ms | 911 ms | 66 MB |
| pypdfium2 (solo texto) | 669 ms | 214 ms | 938 ms | 50 MB |
| pypdf (solo texto) | 6,0 s | 5,4 s | 12,0 s | 66 MB |
| pymupdf4llm, modo clásico liviano (Markdown) | 11,4 s | 1,9 s | 13,8 s | 171 MB |
| pdfplumber (solo texto) | 29,6 s | 19,9 s | 51,4 s | 1.524 MB |
| pymupdf4llm por defecto (Markdown) | 171,8 s | 20,4 s | 212,3 s | 341 MB |

## Decisión

Usar **MuPDF** a través de los bindings oficiales que trae PyMuPDF
(`pymupdf.mupdf`) y convertir a Markdown con un módulo propio:

1. Abrir el PDF sobre los bytes recibidos con `fz_open_memory`, sin copiarlos.
2. Por cada página, pedirle a MuPDF el texto estructurado en JSON
   (`fz_print_stext_page_as_json`). Ese JSON trae, por línea, el texto, el
   tamaño de letra y si es negrita, y se genera en C.
3. Con eso, `App/infrastructure/markdown/converter.py` (lógica pura, testeada sin PDFs) detecta
   títulos por tamaño **relativo** al cuerpo del documento, listas por viñetas,
   negritas cortas y párrafos.

## Alternativas consideradas

### pymupdf4llm (la librería "oficial" de PyMuPDF para Markdown)
- A favor: Markdown de muy buena calidad (tablas, columnas, OCR opcional).
- En contra: 370 veces más lenta en el PDF de 292 páginas (172 s). Incluso en
  su modo más liviano tarda 11,4 s. Con 50 req/s es inviable.
- Rechazada: la calidad extra (tablas) no compensa una capacidad decenas de
  veces menor.

### PyMuPDF `get_text("dict")` para obtener los tamaños de letra
- A favor: API de alto nivel, documentada.
- En contra: crea un diccionario de Python por cada fragmento de texto: un
  38 % más lento que el JSON nativo en el PDF de 292 páginas.
- Rechazada por costo.

### Texto plano (PyMuPDF `get_text`, pypdfium2)
- A favor: lo más rápido.
- En contra: no hay títulos; la consigna pide Markdown.
- Rechazada: nuestro extractor genera Markdown con prácticamente el mismo costo
  (704 ms contra 679 ms en total).

### pdfplumber / pypdf
- En contra: 17 a 75 veces más lentos; pdfplumber llega a 1,5 GB de memoria en
  el PDF de 292 páginas y no entraría en el límite de 1 GB por réplica.
- Rechazadas.

### La heurística de títulos que trae la salida XHTML de MuPDF
- En contra: usa tamaños absolutos (todo lo que supera 12 pt es `h3`), así que
  en documentos con cuerpo de 12 pt marca los párrafos como títulos.
- Rechazada: por eso los títulos se calculan relativos al documento.

## Consecuencias

- La extracción es el cuello de botella esperado y quedó cerca del mínimo
  medible con MuPDF.
- Dependemos de los bindings de bajo nivel de MuPDF (documentados en
  mupdf.readthedocs.io). Para acotar el riesgo, el único módulo que los usa es
  `App/infrastructure/markdown/reader.py`, la versión de PyMuPDF está fijada y hay tests del
  lector con PDFs reales.
- No se reconstruyen tablas ni imágenes (el servicio extrae **texto**). Si la
  cátedra exigiera tablas, habría que medir el costo de detectarlas.
- Optimización posterior (ver informe): limpiar caracteres invisibles con
  `str.replace` en lugar de `str.translate` bajó la conversión a Markdown de
  103 ms a 24 ms en el PDF de 292 páginas.

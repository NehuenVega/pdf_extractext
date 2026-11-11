# Contexto del proyecto — PDFtrack

Este archivo resume **qué es** el sistema, **cómo está organizado** y **qué
significa** cada término que usamos en el código y en los commits. Las
decisiones y sus porqués están en [docs/adr/](docs/adr/).

## Qué hace

Una API (FastAPI) para extraer texto de archivos PDF, con dos formas de uso:

| Endpoint | Para qué | Usa MongoDB |
|---|---|---|
| `POST /api/v1/extract-text` | Texto por página; guarda el documento y lo reutiliza si se vuelve a subir el mismo archivo | Sí (caché por checksum) |
| `GET/PATCH/DELETE /api/v1/documents/...` | CRUD de los documentos guardados | Sí |
| `POST /extract` | PDF → Markdown + cantidad de páginas; es el endpoint de las pruebas de carga | No (siempre extrae) |
| `GET /health` | Chequeo de salud del balanceador | No |

En Docker corren 5 réplicas de la misma imagen detrás de HAProxy, más una
instancia de MongoDB ([docker-compose.yml](docker-compose.yml)).

## Arquitectura: hexagonal (puertos y adaptadores)

```
App/
├── main.py            Composición: arma la app y elige los adaptadores
├── __main__.py        Arranque en Docker (python -m App)
├── api/               Adaptador de entrada HTTP (FastAPI)
│   ├── routers/       extract_router, document_router, markdown_router
│   ├── dependencies.py, errors.py, uploads.py, access_log.py
├── services/          Casos de uso (no conocen HTTP ni MongoDB)
│   ├── pdf_service.py        extraer texto por página + caché
│   ├── markdown_service.py   extraer a Markdown con backpressure
│   └── admission.py          cola acotada en tamaño y tiempo
├── domain/            Centro: modelos, puertos (Protocol) y errores propios
└── infrastructure/    Adaptadores de salida
    ├── mongo_repository.py       MongoDB (caché + CRUD)
    ├── pymupdf_extractor.py      texto por página con PyMuPDF
    ├── process_pool_extractor.py Markdown en un pool de procesos
    ├── worker_pool.py
    └── markdown/                 reader (MuPDF) y converter (Markdown)
```

**Regla de dependencias:** todo apunta hacia `domain`. `services` solo conoce
`domain`; `api` e `infrastructure` conocen `domain` y `services`, nunca al
revés. Solo `main.py` sabe qué adaptador concreto implementa cada puerto, y es
el único lugar que lee la configuración. Los servicios lanzan errores del
dominio (`App/domain/exceptions.py`) y `App/api/errors.py` los traduce a HTTP.

Ver [ADR-0005](docs/adr/0005-arquitectura-hexagonal.md).

## Glosario

- **Documento:** un PDF ya procesado por `/extract-text`, guardado en MongoDB
  con su nombre, sus páginas y su checksum.
- **Checksum:** SHA-256 del archivo. Si llega un archivo con un checksum que ya
  está guardado, se devuelve lo guardado sin volver a extraer (**caché**).
- **Puerto:** interfaz (`Protocol`) definida en `domain/interfaces.py`:
  `IPdfExtractor`, `IMarkdownExtractor`, `IDocumentCache`, `IDocumentRepository`.
- **Adaptador:** implementación concreta de un puerto (Mongo, PyMuPDF, pool).
- **Réplica:** uno de los 5 contenedores de la API (1 CPU, 1 GB).
- **Worker:** proceso aparte, dentro de una réplica, donde corre la extracción
  a Markdown para no bloquear el event loop que atiende HTTP.
- **Control de admisión / backpressure:** cuántos pedidos pueden esperar un
  worker y por cuánto tiempo. Pasado el límite se responde **503** con
  `Retry-After` en lugar de acumular trabajo que llegaría tarde.
- **Cola central:** la cola de HAProxy. Le pasa a cada réplica un pedido por vez
  y deja pasar primero a los PDFs chicos.

## Cómo se trabaja

- Dependencias con **uv** (`pyproject.toml` + `uv.lock`): `uv sync`.
- Tests: `uv run pytest`. Los tests de cada capa usan dobles por los puertos
  (sin MongoDB ni red).
- Todo se configura por variables de entorno ([App/core/config.py](App/core/config.py),
  [.env.example](.env.example)).
- Pruebas de carga y resultados: [docs/INFORME.md](docs/INFORME.md).

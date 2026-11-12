# ADR-0005: Arquitectura hexagonal (puertos y adaptadores)

## Estado
Aceptado

## Fecha
2026-11-10

## Contexto

En la corrección de la primera entrega, la estructura del proyecto se
clasificó como hexagonal con tendencia Onion, pero con defectos que impedían
que se cumpliera de verdad:

1. `services/pdf_service.py` importaba `HTTPException` de FastAPI: el caso de
   uso dependía del framework web.
2. `IDocumentRepository` mezclaba dos responsabilidades: la caché que usa el
   servicio y el CRUD que usa el router.
3. La configuración era un objeto global que se leía desde servicios y
   adaptadores (dependencia oculta).
4. La decisión de estilo no estaba documentada.

Además, en esta entrega se suma el microservicio de extracción a Markdown del
TP de pruebas de carga, que tiene que convivir con lo anterior en un mismo
código.

## Decisión

Adoptamos **arquitectura hexagonal** y la hacemos explícita:

- **Dominio** (`App/domain`): modelos, puertos como `Protocol` y errores
  propios. No importa nada del resto de la aplicación.
- **Casos de uso** (`App/services`): `PdfExtractionService`,
  `MarkdownExtractionService` y `AdmissionController`. Solo conocen el
  dominio; reciben sus dependencias por constructor y lanzan errores del
  dominio, nunca `HTTPException`.
- **Adaptadores de entrada** (`App/api`): routers de FastAPI. Traducen HTTP a
  llamadas a los casos de uso y los errores del dominio a códigos HTTP
  (`App/api/errors.py`).
- **Adaptadores de salida** (`App/infrastructure`): MongoDB, PyMuPDF y el
  pool de procesos que convierte a Markdown.
- **Composición** (`App/main.py`): el único lugar que lee la configuración
  (`get_settings`) y decide qué adaptador implementa cada puerto. Los objetos
  de larga vida (cliente de MongoDB, pool de workers) se crean en el
  `lifespan` y se reparten con `Depends`.

Puertos:

| Puerto | Lo usa | Adaptador |
|---|---|---|
| `IPdfExtractor` | `PdfExtractionService` | `PyMuPdfExtractor` |
| `IDocumentCache` | `PdfExtractionService` | `MongoDocumentRepository` |
| `IDocumentRepository` | `document_router` (CRUD) | `MongoDocumentRepository` |
| `IMarkdownExtractor` | `MarkdownExtractionService` | `ProcessPoolMarkdownExtractor` |

`IDocumentCache` e `IDocumentRepository` salen de dividir la interfaz anterior
(segregación de interfaces): el servicio ya no depende de los métodos del CRUD.

## Alternativas consideradas

### N-capas estricta
- Cada capa solo llama a la de abajo, y la capa de datos queda en la base. El
  dominio terminaría dependiendo de cómo se guardan los datos.
- Rechazada: queremos poder testear los casos de uso con dobles, sin MongoDB.

### Clean Architecture completa (entidades sin Pydantic, DTOs por capa)
- Entidades como clases planas y mapeo explícito en cada borde.
- Rechazada por ahora: para un proyecto de este tamaño, duplicar cada modelo
  agrega código sin un beneficio claro. Aceptamos que `domain/models.py` use
  Pydantic (ver Consecuencias).

## Consecuencias

- Los tests de servicios no necesitan FastAPI ni MongoDB: usan dobles que
  implementan los puertos (`tests/test_service.py`, `tests/test_markdown_service.py`).
- Para cambiar la base de datos o el motor de extracción alcanza con escribir
  otro adaptador y cambiar una línea en `main.py`.
- `domain/models.py` sigue usando `pydantic.BaseModel`: es una dependencia
  externa en el centro. Lo aceptamos porque FastAPI usa esos mismos modelos
  para validar y documentar las respuestas.
- `POST /extract` no usa la caché de MongoDB a propósito: es el endpoint que
  se mide en las pruebas de carga y tiene que extraer siempre (ver ADR-0006).

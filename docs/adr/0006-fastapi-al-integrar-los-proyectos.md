# ADR-0006: FastAPI para todo el servicio al integrar los dos proyectos

## Estado
Aceptado. Reemplaza al [ADR-0004](0004-lenguaje-y-framework.md) en lo que
respecta al framework.

## Fecha
2026-11-10

## Contexto

El microservicio del TP de pruebas de carga se hizo como un proyecto aparte con
Starlette (ADR-0004). La cátedra pidió que forme parte de PDFtrack, que ya
estaba hecho con FastAPI + MongoDB. Mantener dos aplicaciones (dos imágenes,
dos configuraciones, dos formas de testear) no tiene sentido para un mismo
dominio.

Los dos motivos por los que el ADR-0004 descartó FastAPI eran:

1. El parser de formularios guarda en disco los archivos de más de 1 MB.
2. La validación automática no aporta en un endpoint que recibe bytes.

## Decisión

- Una sola aplicación **FastAPI** (`App/`) con todas las rutas, una sola imagen
  Docker y una sola configuración.
- `POST /extract` **no** usa `UploadFile`: recibe el `Request` y lee el cuerpo
  a mano (`App/api/uploads.py`), igual que antes. Así se mantiene la lectura
  en memoria sin archivos temporales (motivo 1). Los demás endpoints siguen
  usando `UploadFile` como antes.
- El formato del cuerpo se declara con `openapi_extra` para que `/docs` lo
  muestre aunque FastAPI no lo valide (motivo 2: no se pierde nada).
- Los errores pasan al formato estándar de FastAPI, `{"detail": "..."}`, en
  todos los endpoints y también en los 503 que genera HAProxy.
- `POST /extract` no consulta MongoDB: extrae siempre.
- uvicorn se instala con el extra `standard` (httptools y uvloop en Linux,
  los mismos parsers en C que usaba el TP).

## Alternativas consideradas

### Dos servicios separados (API PDFtrack + microservicio de extracción)
- A favor: cada uno escala por separado.
- En contra: dos bases de código para el mismo dominio, el extractor de texto
  por página y el de Markdown duplicarían validaciones y configuración, y la
  consigna pide que sea un solo proyecto.
- Rechazada.

### Pasar PDFtrack a Starlette
- En contra: cambiaría todo el código existente (routers, `Depends`,
  validación de `PATCH`, `/docs`) sin ningún beneficio medible.
- Rechazada.

### Usar la caché de MongoDB también en `/extract`
- A favor: un PDF repetido respondería en milisegundos.
- En contra: las pruebas de carga repiten siempre los mismos 4 PDFs, así que
  medirían MongoDB y no la extracción, y cada réplica dependería de la base
  para atender `/extract`.
- Rechazada.

## Consecuencias

- FastAPI agrega un poco de trabajo por pedido (inyección de dependencias,
  middleware), despreciable frente a los 40–220 ms de extracción. Se volvió a
  medir el sistema completo con k6 y Vegeta (informe, sección 6.3).
- Toda la documentación de la API queda en `/docs`, incluido `/extract`.
- Las dependencias se manejan con uv (`pyproject.toml` + `uv.lock`) en lugar de
  `requirements.txt`.

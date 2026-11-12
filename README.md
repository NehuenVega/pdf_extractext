# API PDFtrack

Este desarrollo consiste en una plataforma web orientada a la extracción de texto desde archivos PDF. La solución está construida sobre FastAPI y MongoDB, cumpliendo estrictamente con los objetivos planteados para la primera etapa del Proyecto de Desarrollo de Software.

En la segunda etapa se le sumó el microservicio del TP de **test de carga, estrés y optimización**: el endpoint `POST /extract` (PDF → Markdown), preparado para correr en 5 réplicas detrás de un balanceador y medido con k6 y Vegeta.

## Equipo de Trabajo

- Lucas Ruiz
- Nehuén Vega
- Ramiro Juárez
- Maximiliano Serna
- Facundo Ferreyra
- Juan Ignacio Pérez

## Endpoints

| Método y ruta | Qué hace |
|---|---|
| `POST /api/v1/extract-text` | Extrae el texto por página y lo guarda en MongoDB. Si el mismo archivo ya se subió (mismo checksum), devuelve lo guardado. |
| `GET /api/v1/documents/` | Lista los documentos guardados. |
| `GET /api/v1/documents/{id}` | Detalle de un documento. |
| `PATCH /api/v1/documents/{id}?new_filename=...` | Cambia el nombre guardado. |
| `DELETE /api/v1/documents/{id}` | Borra un documento. |
| `POST /extract` | Devuelve `{"content": <markdown>, "page_count": N}`. Acepta el PDF como binario o multipart. No usa la caché: siempre extrae. |
| `GET /health` | Chequeo de salud que usa el balanceador. |

Los errores siempre tienen la forma `{"detail": "..."}`. La documentación interactiva está en `/docs`.

La arquitectura (hexagonal: puertos y adaptadores) y el vocabulario del proyecto están explicados en [CONTEXT.md](CONTEXT.md); las decisiones, en [docs/adr/](docs/adr/).

## Requerimientos del Sistema

Para poner en marcha el proyecto, vas a necesitar contar con:

- **Docker:** indispensable para levantar MongoDB (o el sistema completo).
- **uv:** lo usamos como gestor de paquetes y entorno para Python por su velocidad.

## Guía de Configuración y Despliegue

### Opción A: sistema completo con Docker

Levanta 5 réplicas de la API (1 CPU y 1 GB cada una), HAProxy como balanceador y MongoDB:

```bash
docker compose up --build
```

La API queda en http://localhost:8080 (por ejemplo, http://localhost:8080/docs) y el panel de HAProxy en http://localhost:8404.

### Opción B: desarrollo local

1. Inicialización de la Base de Datos. Como usamos MongoDB para gestionar los documentos y sus identificadores únicos (checksums), lo primero que tenés que hacer es correr el contenedor:

   ```bash
   docker run -d --name pdftrack-mongo -p 27017:27017 mongo:8.0
   ```

2. Instalación de Dependencias. Una vez que tengas Docker funcionando, instalá los paquetes necesarios usando el gestor uv (lee las dependencias de `pyproject.toml` y las versiones exactas de `uv.lock`):

   ```bash
   uv sync
   ```

3. Lanzamiento de la API. Con todo listo, ya podés levantar el servidor de FastAPI:

   ```bash
   uv run uvicorn App.main:app --reload
   ```

   Cuando el proceso termine de arrancar, podés entrar a http://localhost:8000/docs para ver la documentación interactiva.

Toda la configuración se toma de variables de entorno (ver [.env.example](.env.example) y `App/core/config.py`).

## Tests

```bash
uv run pytest
```

Los tests no necesitan MongoDB: los servicios se prueban con dobles que implementan los puertos del dominio.

## Pruebas de carga

Con el sistema levantado (opción A), en otra terminal:

```bash
docker compose --profile stress run --rm k6       # spike: 0 → 100 usuarios
docker compose --profile stress run --rm vegeta   # 50 req/s durante 30 s
```

Usan los 4 PDFs de la cátedra (`tests/stress/pdfs`). El análisis completo, las mediciones y la comparación con el benchmark del profesor están en [docs/INFORME.md](docs/INFORME.md).

## Stack Tecnológico

- **Lenguaje:** Python 3.13
- **Framework:** FastAPI + uvicorn
- **Gestión de paquetes:** UV
- **Base de Datos:** MongoDB (NoSQL)
- **Extracción:** PyMuPDF (MuPDF)
- **Infraestructura:** Docker Compose y HAProxy
- **Pruebas de carga:** k6 y Vegeta
- **IA:** Modelo a definir (con posibilidad de integrar Ollama a futuro).

## Metodología y Estándares

El desarrollo no es al azar; nos basamos en pilares de ingeniería sólidos:

- **Flujo de trabajo:** Desarrollo guiado por pruebas (TDD) y gestión centralizada en GitHub.
- **Arquitectura:** Hexagonal (puertos y adaptadores) y los principios de 12-Factor App.
- **Código Limpio:** Aplicamos criterios KISS, DRY, YAGNI y los principios SOLID para asegurar un código mantenible y escalable.

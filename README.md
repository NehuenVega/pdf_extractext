# PDFtrack API - Etapa 1

Aplicación web para la extracción de texto desde archivos PDF, desarrollada con FastAPI y MongoDB, cumpliendo con los requerimientos de la Etapa N° 1 del Proyecto de Desarrollo de Software.

## Requisitos Previos
* *Docker:* Para ejecutar la base de datos no relacional (MongoDB).
* *uv:* Gestor de paquetes y proyectos de Python.

## Instrucciones de Ejecución

### 1. Levantar la Base de Datos (Docker)
El proyecto utiliza MongoDB para persistir los documentos y sus checksums. Ejecute el siguiente comando para iniciar el contenedor en segundo plano:

powershell
docker run -d --name pdftrack-mongo -p 27017:27017 mongo:latest


### 2. Instalar Dependencias

Con Docker corriendo y uv activo, instale las librerías necesarias:

bash
uv pip install -r requirements.txt


### 3. Ejecutar la API

Inicie el servidor de desarrollo de FastAPI:

bash
uv run uvicorn App.main:app --reload


El servicio estará disponible en http://localhost:8000/docs.

---

## Tecnologias:
- Python
- UV
- Modelo de IA (a definir)
- Ollama (opcional, a definir a futuro)
- Base de datos no relacional MongoDB

## Metodologías: 

- TDD
- Proyecto digirido en Github
- Los seis primeros principios de 12 factor APP

## Principios de programación:

- KISS
- DRY
- YAGNI
- SOLID

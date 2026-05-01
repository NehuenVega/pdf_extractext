API PDFtrack - Fase 1
Este desarrollo consiste en una plataforma web orientada a la extracción de texto desde archivos PDF. La solución está construida sobre FastAPI y MongoDB, cumpliendo estrictamente con los objetivos planteados para la primera etapa del Proyecto de Desarrollo de Software.

Equipo de Trabajo:
Lucas Ruiz
Nehuén Vega
Ramiro Juárez
Maximiliano Serna
Facundo Ferreyra
Juan Ignacio Pérez

Requerimientos del Sistema
Para poner en marcha el proyecto, vas a necesitar contar con:

Docker: Indispensable para levantar el contenedor de la base de datos (MongoDB).

uv: Lo usamos como gestor de paquetes y entorno para Python por su velocidad.

Guía de Configuración y Despliegue
1. Inicialización de la Base de Datos
Como usamos MongoDB para gestionar los documentos y sus identificadores únicos (checksums), lo primero que tenés que hacer es correr el contenedor:

PowerShell
docker run -d --name pdftrack-mongo -p 27017:27017 mongo:latest
2. Instalación de Dependencias
Una vez que tengas Docker funcionando, instalá los paquetes necesarios usando el gestor uv:

Bash
uv pip install -r requirements.txt
3. Lanzamiento de la API
Con todo listo, ya podés levantar el servidor de FastAPI:

Bash
uv run uvicorn App.main:app --reload
Cuando el proceso termine de arrancar, podés entrar a http://localhost:8000/docs para ver la documentación interactiva.

Stack Tecnológico
Lenguaje: Python

Gestión de paquetes: UV

Base de Datos: MongoDB (NoSQL)

IA: Modelo a definir (con posibilidad de integrar Ollama a futuro).

Metodología y Estándares
El desarrollo no es al azar; nos basamos en pilares de ingeniería sólidos:

Flujo de trabajo: Desarrollo guiado por pruebas (TDD) y gestión centralizada en GitHub.

Arquitectura: Implementación de los primeros seis principios de 12-Factor App.

Código Limpio: Aplicamos criterios KISS, DRY, YAGNI y los principios SOLID para asegurar un código mantenible y escalable.

# Imagen de la API (FastAPI): la misma para las 5 réplicas.
#
# Versión exacta de Python para que todas las réplicas (y todas las
# mediciones) corran sobre el mismo intérprete.
FROM python:3.13.13-slim

# uv se copia de su imagen oficial (versión fija) en lugar de instalarlo con pip.
COPY --from=ghcr.io/astral-sh/uv:0.9.30 /uv /bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Primero solo las dependencias: Docker reutiliza esta capa mientras
# pyproject.toml y uv.lock no cambien, así un cambio de código no reinstala
# todo. --locked falla si uv.lock no está al día con pyproject.toml.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY App/ App/

# La API no necesita privilegios de root.
RUN useradd --system --uid 10001 --no-create-home app
USER app

# Port binding (12-Factor, VII): el puerto se configura con PORT.
EXPOSE 8000
CMD ["python", "-m", "App"]

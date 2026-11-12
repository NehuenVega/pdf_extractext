"""Página /docs: la documentación interactiva de Swagger UI con estilo propio.

FastAPI arma /docs solo; acá se reemplaza por la misma página con un
encabezado y una hoja de estilos (docs_theme.css) para que sea más legible.
El contenido sale igual del esquema OpenAPI: no hay que mantener nada a mano.
"""

from html import escape
from pathlib import Path

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse

THEME_CSS = Path(__file__).with_name("docs_theme.css").read_text(encoding="utf-8")
SPANISH_JS = Path(__file__).with_name("docs_es.js").read_text(encoding="utf-8")

# Textos que FastAPI genera solo en el esquema OpenAPI.
SPANISH_RESPONSE_DESCRIPTIONS = {
    "Successful Response": "Respuesta correcta",
    "Validation Error": "Error de validación",
}

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    'family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap">\n'
)

SWAGGER_UI_PARAMETERS = {
    "docExpansion": "list",  # endpoints cerrados: se ve el índice completo
    "defaultModelsExpandDepth": -1,  # sin la sección "Schemas" al final
    "tryItOutEnabled": True,  # se puede probar sin apretar "Try it out"
    "displayRequestDuration": True,  # muestra cuánto tardó cada pedido
    "syntaxHighlight": {"theme": "nord"},
}


# Ícono del encabezado: una hoja con la esquina doblada y renglones.
LOGO_SVG = (
    '<svg viewBox="0 0 32 32" width="28" height="28" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M8 3h11l7 7v17a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/>'
    '<path d="M19 3v7h7"/><path d="M11 16h10M11 20h10M11 24h6"/></svg>'
)

# Enlace directo a POST /extract. Swagger UI solo lee el "#/..." al cargar la
# página, así que el botón abre el endpoint y baja hasta él con este script.
TRY_EXTRACT_LINK = "#/Markdown/extract_markdown_extract_post"
OPEN_ENDPOINT_JS = """<script>
function ptOpenEndpoint(event, id) {
  const block = document.getElementById(id);
  if (!block) return;
  event.preventDefault();
  if (!block.classList.contains('is-open')) block.querySelector('.opblock-summary-control').click();
  // Se espera a que Swagger termine de abrirlo para bajar hasta el lugar justo.
  setTimeout(() => block.scrollIntoView({ behavior: 'smooth', block: 'start' }), 150);
}
</script>
"""


def register_docs(app: FastAPI, subtitle: str, highlights: list[str]) -> None:
    """Agrega GET /docs. La app tiene que crearse con ``docs_url=None``."""
    page = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} · Documentación",
        swagger_ui_parameters=SWAGGER_UI_PARAMETERS,
    )
    html = page.body.decode()
    html = html.replace("<html>", '<html lang="es">', 1)
    html = html.replace("</head>", f"{FONTS}<style>\n{THEME_CSS}</style>\n</head>", 1)
    html = html.replace('<div id="swagger-ui">', _header(app, subtitle, highlights) + '<div id="swagger-ui">', 1)
    html = html.replace("<script src=", _footer(app) + "<script src=", 1)
    html = html.replace("</body>", f"<script>\n{SPANISH_JS}</script>\n</body>", 1)
    _translate_openapi(app)

    @app.get("/docs", include_in_schema=False)
    async def docs() -> HTMLResponse:
        return HTMLResponse(html)


def _translate_openapi(app: FastAPI) -> None:
    """Pasa al castellano las descripciones de respuesta que agrega FastAPI."""
    build_schema = app.openapi

    def openapi() -> dict:
        schema = build_schema()  # FastAPI lo arma una vez y lo guarda
        for operations in schema.get("paths", {}).values():
            for operation in operations.values():
                for response in operation.get("responses", {}).values():
                    description = response.get("description")
                    response["description"] = SPANISH_RESPONSE_DESCRIPTIONS.get(description, description)
        return schema

    app.openapi = openapi


def _header(app: FastAPI, subtitle: str, highlights: list[str]) -> str:
    chips = "".join(f"<li>{escape(item)}</li>" for item in highlights)
    return OPEN_ENDPOINT_JS + f"""<header class="pt-header">
  <div class="pt-wrap">
    <div class="pt-brand">
      <div class="pt-logo" aria-hidden="true">{LOGO_SVG}</div>
      <div>
        <div class="pt-kicker">UTN FRSR · Desarrollo de Software</div>
        <h1>{escape(app.title)} <span class="pt-version">v{escape(app.version)}</span></h1>
      </div>
    </div>
    <p class="pt-lead">{escape(subtitle)}</p>
    <ul class="pt-chips">{chips}</ul>
    <nav class="pt-links">
      <a class="pt-btn" href="{TRY_EXTRACT_LINK}"
         onclick="ptOpenEndpoint(event, 'operations-Markdown-extract_markdown_extract_post')">Probar POST /extract</a>
      <a class="pt-btn pt-btn-ghost" href="{escape(app.openapi_url)}">openapi.json</a>
      <a class="pt-btn pt-btn-ghost" href="/health">/health</a>
    </nav>
  </div>
</header>
"""


def _footer(app: FastAPI) -> str:
    return f"""<footer class="pt-footer">
  <div class="pt-wrap">{escape(app.title)} · API PDFtrack · UTN FRSR · Desarrollo de Software</div>
</footer>
"""

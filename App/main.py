from fastapi import FastAPI
from App.api.errors import register_exception_handlers
from App.api.routers import extract_router, document_router
from App.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)
register_exception_handlers(app)

# Rutas
app.include_router(extract_router.router, prefix="/api")
app.include_router(document_router.router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "PDFtrack API is running"}

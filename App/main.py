from fastapi import FastAPI
from App.api.routers import extract_router, document_router # Importamos el nuevo
from App.api.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)

# Rutas
app.include_router(extract_router.router, prefix="/api")
app.include_router(document_router.router, prefix="/api") # Conectamos el CRUD

@app.get("/")
def read_root():
    return {"message": "PDFtrack API is running"}

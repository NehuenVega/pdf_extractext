from contextlib import asynccontextmanager

from fastapi import FastAPI
from App.api.errors import register_exception_handlers
from App.api.routers import extract_router, document_router
from App.core.config import Settings, get_settings
from App.infrastructure.mongo_repository import MongoDocumentRepository


def create_app(settings: Settings | None = None) -> FastAPI:
    """Arma la aplicación: es el único lugar que lee la configuración y elige
    qué adaptador concreto (Mongo, PyMuPDF) implementa cada puerto."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.repository = MongoDocumentRepository(settings.MONGO_URI, settings.DB_NAME)
        yield
        app.state.repository.close()

    app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION, lifespan=lifespan)
    app.state.settings = settings
    register_exception_handlers(app)

    app.include_router(extract_router.router, prefix=settings.API_V1_STR)
    app.include_router(document_router.router, prefix=settings.API_V1_STR)

    @app.get("/")
    def read_root():
        return {"message": "PDFtrack API is running"}

    return app


app = create_app()

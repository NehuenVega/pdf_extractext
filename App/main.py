import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from App.api.access_log import AccessLogMiddleware
from App.api.errors import register_exception_handlers
from App.api.routers import extract_router, document_router, markdown_router
from App.core.config import Settings, get_settings
from App.infrastructure.mongo_repository import MongoDocumentRepository
from App.infrastructure.process_pool_extractor import ProcessPoolMarkdownExtractor
from App.services.admission import AdmissionController
from App.services.markdown_service import MarkdownExtractionService

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Arma la aplicación: es el único lugar que lee la configuración y elige
    qué adaptador concreto (Mongo, PyMuPDF, pool de procesos) implementa cada puerto."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Los workers arrancan antes de aceptar tráfico y se apagan después de
        # terminar los pedidos en curso (12-Factor, IX: desechabilidad).
        markdown_extractor = ProcessPoolMarkdownExtractor(workers=settings.EXTRACTION_WORKERS)
        await markdown_extractor.start()
        admission = AdmissionController(
            max_concurrent=settings.EXTRACTION_WORKERS,
            max_waiting=settings.MAX_QUEUE_SIZE,
            wait_timeout=settings.QUEUE_TIMEOUT_SECONDS,
        )
        app.state.markdown_service = MarkdownExtractionService(markdown_extractor, admission)
        app.state.repository = MongoDocumentRepository(settings.MONGO_URI, settings.DB_NAME)
        logger.info("Servicio listo", extra={"fields": settings.model_dump(exclude={"MONGO_URI"})})
        yield
        logger.info("Apagando: se esperan los pedidos en curso")
        markdown_extractor.close()
        app.state.repository.close()

    app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION, lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(AccessLogMiddleware)
    register_exception_handlers(app)

    app.include_router(extract_router.router, prefix=settings.API_V1_STR)
    app.include_router(document_router.router, prefix=settings.API_V1_STR)
    app.include_router(markdown_router.router)

    @app.get("/")
    def read_root():
        return {"message": "PDFtrack API is running"}

    return app


app = create_app()

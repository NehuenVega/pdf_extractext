from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Toda la configuración entra por variables de entorno (12-Factor, III): la
# misma imagen Docker sirve para desarrollo y para las pruebas de carga. Si un
# valor es inválido, la aplicación no arranca.
class Settings(BaseSettings):
    PROJECT_NAME: str = "PDF extractext"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    # El PDF más grande de las pruebas de carga pesa 8,7 MB.
    MAX_FILE_SIZE_MB: int = Field(default=32, ge=1)

    MONGO_URI: str = "mongodb://localhost:27017"
    DB_NAME: str = "pdftrack_db"

    # Servidor (python -m App). Port binding: 12-Factor, VII.
    HOST: str = "0.0.0.0"
    PORT: int = Field(default=8000, ge=1, le=65_535)
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # POST /extract. Procesos que extraen en paralelo dentro de cada réplica:
    # con 1 CPU por contenedor, más de uno solo se reparte el mismo núcleo.
    EXTRACTION_WORKERS: int = Field(default=1, ge=1)
    # Backpressure: cuántos pedidos pueden esperar un worker libre y por
    # cuánto tiempo. Pasado ese tiempo el pedido ya no le sirve al cliente
    # (Vegeta corta a los 30 s) y se responde 503.
    MAX_QUEUE_SIZE: int = Field(default=8, ge=0)
    QUEUE_TIMEOUT_SECONDS: float = Field(default=25.0, gt=0, allow_inf_nan=False)
    # Tiempo máximo para recibir el archivo completo: un cliente que lo manda
    # de a gotas bloquearía la réplica, que procesa un pedido por vez.
    UPLOAD_TIMEOUT_SECONDS: float = Field(default=15.0, gt=0, allow_inf_nan=False)

    model_config = SettingsConfigDict(case_sensitive=True)

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

@lru_cache
def get_settings() -> Settings:
    """Lee la configuración del entorno una sola vez por proceso."""
    return Settings()

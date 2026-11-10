from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "PDF extractext"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    MAX_FILE_SIZE_MB: int = 5

    MONGO_URI: str = "mongodb://localhost:27017"
    DB_NAME: str = "pdftrack_db"

    model_config = SettingsConfigDict(case_sensitive=True)

@lru_cache
def get_settings() -> Settings:
    """Lee la configuración del entorno una sola vez por proceso."""
    return Settings()

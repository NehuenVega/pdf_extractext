from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "PDF extractext"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    MAX_FILE_SIZE_MB: int = 5 
    
    # Nuevas variables para MongoDB
    MONGO_URI: str = "mongodb://localhost:27017"
    DB_NAME: str = "pdftrack_db"

    model_config = ConfigDict(case_sensitive=True)

settings = Settings()

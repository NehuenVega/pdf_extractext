"""Core configuration module."""

from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "PDF Summarizer"
    upload_dir: Path = Path("uploads")
    max_file_size_mb: int = 10
    nvidia_api_key: str
    nvidia_api_url: str = "https://integrate.api.nvidia.com/v1"
    ai_model: str = "meta/llama-3.2-90b-vision-instruct"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""File storage handler for PDF uploads."""

import aiofiles
from pathlib import Path
from app.core import get_settings


class FileHandler:
    def __init__(self, upload_dir: Path | None = None):
        settings = get_settings()
        self._upload_dir = upload_dir or settings.upload_dir
        self._upload_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, content: bytes, filename: str) -> Path:
        file_path = self._upload_dir / filename
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
        return file_path

    async def read(self, filename: str) -> bytes:
        file_path = self._upload_dir / filename
        async with aiofiles.open(file_path, "rb") as f:
            return await f.read()

    def delete(self, filename: str) -> None:
        file_path = self._upload_dir / filename
        if file_path.exists():
            file_path.unlink()

    def exists(self, filename: str) -> bool:
        return (self._upload_dir / filename).exists()

"""Summary Repository interface - abstraction for persistence."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class Summary:
    id: UUID
    original_filename: str
    summary_text: str
    extracted_text: str
    created_at: datetime


class SummaryRepository(ABC):
    @abstractmethod
    async def save(self, summary: Summary) -> Summary:
        pass

    @abstractmethod
    async def get_by_id(self, summary_id: UUID) -> Summary | None:
        pass

    @abstractmethod
    async def get_all(self, limit: int = 100) -> list[Summary]:
        pass

"""In-memory implementation of the Summary Repository."""

from datetime import datetime, timezone
from uuid import UUID, uuid4
from app.application.interfaces.summary_repository import Summary, SummaryRepository


class InMemorySummaryRepository(SummaryRepository):
    def __init__(self):
        self._storage: dict[UUID, Summary] = {}

    async def save(self, summary: Summary) -> Summary:
        summary.id = uuid4()
        summary.created_at = datetime.now(timezone.utc)
        self._storage[summary.id] = summary
        return summary

    async def get_by_id(self, summary_id: UUID) -> Summary | None:
        return self._storage.get(summary_id)

    async def get_all(self, limit: int = 100) -> list[Summary]:
        summaries = sorted(
            self._storage.values(),
            key=lambda s: s.created_at or datetime.min,
            reverse=True,
        )
        return summaries[:limit]

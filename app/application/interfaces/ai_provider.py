"""AI Provider interface - abstraction for AI model providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class AIResponse:
    content: str
    model: str
    tokens_used: int | None = None


class AIProvider(ABC):
    @abstractmethod
    async def generate_summary(self, text: str, max_length: int = 500) -> AIResponse:
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        pass

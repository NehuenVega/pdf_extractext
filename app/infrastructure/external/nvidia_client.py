"""Nvidia NIM API client - OpenAI-compatible API implementation."""

import httpx
from app.application.interfaces.ai_provider import AIProvider, AIResponse
from app.core import get_settings


class NvidiaAIProvider(AIProvider):
    def __init__(self, api_key: str | None = None):
        settings = get_settings()
        self._api_key = api_key or settings.nvidia_api_key
        self._base_url = settings.nvidia_api_url
        self._model = settings.ai_model

    async def generate_summary(self, text: str, max_length: int = 500) -> AIResponse:
        prompt = self._build_summary_prompt(text, max_length)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that summarizes documents.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 1024,
                    "temperature": 0.3,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()

            return AIResponse(
                content=data["choices"][0]["message"]["content"],
                model=self._model,
                tokens_used=data.get("usage", {}).get("total_tokens"),
            )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._base_url}/models",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    timeout=10.0,
                )
                return response.status_code == 200
        except Exception:
            return False

    def _build_summary_prompt(self, text: str, max_length: int) -> str:
        return (
            f"Please provide a concise summary of the following document "
            f"(maximum {max_length} words):\n\n{text}"
        )

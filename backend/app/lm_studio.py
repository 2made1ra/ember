from __future__ import annotations

from typing import Any

import httpx

from .config import Settings
from .errors import DependencyUnavailableError


class LMStudioClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.lm_studio_base_url.rstrip("/")
        self.embedding_base_url = settings.embedding_base_url.rstrip("/")
        self.chat_base_url = settings.chat_base_url.rstrip("/")

    def embed(self, texts: list[str]) -> list[list[float]]:
        headers = {}
        if self.settings.embedding_api_key:
            headers["Authorization"] = f"Bearer {self.settings.embedding_api_key}"
        try:
            response = httpx.post(
                f"{self.embedding_base_url}/embeddings",
                json={
                    "model": self.settings.embedding_model,
                    "input": texts,
                    "encoding_format": "float",
                },
                headers=headers,
                timeout=120,
            )
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise DependencyUnavailableError(
                "Embedding API недоступен: не удалось подключиться к "
                f"{self.embedding_base_url}. Если используете LM Studio, запустите "
                "OpenAI-compatible server. Проверьте адрес embedding endpoint и модель "
                f"`{self.settings.embedding_model}`."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise DependencyUnavailableError(
                "Embedding API отклонил запрос: "
                f"HTTP {exc.response.status_code}. Проверьте API key, base URL и модель "
                f"`{self.settings.embedding_model}`."
            ) from exc
        data = response.json()["data"]
        return [item["embedding"] for item in sorted(data, key=lambda x: x["index"])]

    def complete(self, system: str, user: str) -> str:
        headers = {}
        if self.settings.chat_api_key:
            headers["Authorization"] = f"Bearer {self.settings.chat_api_key}"
        try:
            response = httpx.post(
                f"{self.chat_base_url}/chat/completions",
                json={
                    "model": self.settings.chat_model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.2,
                },
                headers=headers,
                timeout=120,
            )
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise DependencyUnavailableError(
                "Chat API недоступен: не удалось подключиться к "
                f"{self.chat_base_url}. Проверьте chat endpoint и модель "
                f"`{self.settings.chat_model}`."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise DependencyUnavailableError(
                "Chat API отклонил chat completion: "
                f"HTTP {exc.response.status_code}. Проверьте модель "
                f"`{self.settings.chat_model}`."
            ) from exc
        payload: dict[str, Any] = response.json()
        return payload["choices"][0]["message"]["content"].strip()

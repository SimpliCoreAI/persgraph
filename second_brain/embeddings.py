"""Ollama embedding client."""

from __future__ import annotations

from typing import Any

from .config import settings


class EmbeddingClient:
    """Thin wrapper around Ollama for embeddings. Lazy-connects on first use."""

    def __init__(self) -> None:
        self._client = None  # lazy — don't connect until first use
        self._model = settings.embed_model

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from ollama import Client
            except Exception as exc:  # pragma: no cover - import guard for offline testing
                raise RuntimeError("ollama client library is unavailable") from exc
            self._client = Client(host=settings.ollama_base_url)
        return self._client

    def embed(self, text: str) -> list[float]:
        """Return embedding vector for a single text."""
        response = self._get_client().embed(model=self._model, input=[text])
        return response["embeddings"][0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return embeddings for a list of texts in a single batch call."""
        if not texts:
            return []
        response = self._get_client().embed(model=self._model, input=texts)
        return response["embeddings"]


# Singleton
embedder = EmbeddingClient()

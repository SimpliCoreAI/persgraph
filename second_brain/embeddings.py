"""Ollama embedding client."""

from ollama import Client

from .config import settings


class EmbeddingClient:
    """Thin wrapper around Ollama for embeddings."""

    def __init__(self) -> None:
        self._client = Client(host=settings.ollama_base_url)
        self._model = settings.embed_model

    def embed(self, text: str) -> list[float]:
        """Return embedding vector for a single text."""
        response = self._client.embed(model=self._model, input=[text])
        return response["embeddings"][0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return embeddings for a list of texts in a single batch call."""
        if not texts:
            return []
        response = self._client.embed(model=self._model, input=texts)
        return response["embeddings"]


# Singleton
embedder = EmbeddingClient()

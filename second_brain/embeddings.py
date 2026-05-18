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
        response = self._client.embeddings(model=self._model, prompt=text)
        return response["embedding"]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return embeddings for a list of texts."""
        return [self.embed(t) for t in texts]


# Singleton
embedder = EmbeddingClient()

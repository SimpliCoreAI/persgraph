"""ChromaDB vector store wrapper."""

from typing import Any, Optional

import chromadb
from chromadb.api.models.Collection import Collection

from .config import settings


class VectorStore:
    """Manages ChromaDB collections."""

    def __init__(self) -> None:
        self._client = None  # lazy — don't connect until first use

    def _get_client(self):
        if self._client is None:
            self._client = chromadb.HttpClient(
                host=settings.chroma_host,
                port=settings.chroma_port,
            )
        return self._client

    def get_or_create(self, name: str) -> Collection:
        return self._get_client().get_or_create_collection(name)

    def get(self, name: str) -> Optional[Collection]:
        try:
            return self._get_client().get_collection(name)
        except Exception:
            return None

    def upsert(
        self,
        collection_name: str,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        col = self.get_or_create(collection_name)
        col.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def query(
        self,
        collection_name: str,
        embedding: list[float],
        top_k: int = 5,
        where: dict | None = None,
    ) -> list[dict[str, Any]]:
        """Query a collection and return ranked results."""
        col = self.get(collection_name)
        if col is None or col.count() == 0:
            return []

        query_kwargs: dict[str, Any] = dict(
            query_embeddings=[embedding],
            n_results=min(top_k, col.count()),
            include=["documents", "metadatas", "distances"],
        )
        if where:
            query_kwargs["where"] = where

        try:
            res = col.query(**query_kwargs)
        except Exception:
            # where filter may return 0 results in some ChromaDB versions — fall back gracefully
            return []

        results = []
        for doc, meta, dist in zip(
            res["documents"][0],
            res["metadatas"][0],
            res["distances"][0],
        ):
            results.append({
                "collection": collection_name,
                "text": doc,
                "metadata": meta,
                "score": round(1 - dist, 4),
            })

        return results

    def query_all(
        self,
        embedding: list[float],
        top_k: int = 5,
        where: dict | None = None,
    ) -> list[dict[str, Any]]:
        """Query all collections and return merged, ranked results."""
        all_results: list[dict[str, Any]] = []
        for name in settings.all_collections:
            all_results.extend(self.query(name, embedding, top_k, where=where))

        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:top_k]


# Singleton
vectorstore = VectorStore()

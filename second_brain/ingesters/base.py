"""Abstract base class for all ingesters."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class IngestResult:
    source: str
    chunks_total: int
    chunks_new: int
    collection: str
    tags: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


class BaseIngester(ABC):
    """All ingesters must implement this interface."""

    @abstractmethod
    def ingest(self, source: str, tags: Optional[list[str]] = None) -> IngestResult:
        """
        Ingest content from source into the vector store.

        Args:
            source: File path, URL, or other source identifier
            tags: Optional list of tags for filtering/retrieval

        Returns:
            IngestResult with stats and any errors
        """
        ...

    def _chunk_text(self, text: str, size: int, overlap: int) -> list[str]:
        """Split text into overlapping word-based chunks."""
        words = text.split()
        chunks = []
        i = 0
        while i < len(words):
            chunk = " ".join(words[i : i + size])
            if chunk.strip():
                chunks.append(chunk)
            i += size - overlap
        return chunks

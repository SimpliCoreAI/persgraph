"""PDF ingester — extracts text, chunks, embeds, and stores."""

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from typing import Optional

import pypdf

from ..config import settings
from ..embeddings import embedder
from ..vectorstore import vectorstore
from .base import BaseIngester, IngestResult


class PDFIngester(BaseIngester):
    """Ingest PDF files into the vector store."""

    def __init__(self, collection_override: Optional[str] = None) -> None:
        self._collection = collection_override or settings.collection_pdfs

    def ingest(self, source: str, tags: Optional[list[str]] = None) -> IngestResult:
        path = Path(source).resolve()
        tags = tags or []

        if not path.exists():
            return IngestResult(
                source=source,
                chunks_total=0,
                chunks_new=0,
                collection=self._collection,
                tags=tags,
                errors=[f"File not found: {path}"],
            )

        # Extract text
        text = self._extract_text(path)
        if not text.strip():
            return IngestResult(
                source=source,
                chunks_total=0,
                chunks_new=0,
                collection=self._collection,
                tags=tags,
                errors=["No text extracted — may be a scanned PDF (OCR not supported yet)"],
            )

        # Chunk
        chunks = self._chunk_text(text, settings.chunk_size, settings.chunk_overlap)
        file_hash = hashlib.md5(path.read_bytes()).hexdigest()

        # Check existing docs to skip duplicates
        collection = vectorstore.get_or_create(self._collection)
        existing_ids = set(collection.get()["ids"])

        ids, embeddings, documents, metadatas = [], [], [], []

        for i, chunk in enumerate(chunks):
            doc_id = f"{file_hash}_{i}"
            if doc_id in existing_ids:
                continue

            ids.append(doc_id)
            embeddings.append(embedder.embed(chunk))
            documents.append(chunk)
            metadatas.append({
                "source": str(path),
                "filename": path.name,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "tags": ",".join(tags),
            })

        if ids:
            vectorstore.upsert(
                collection_name=self._collection,
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )

        return IngestResult(
            source=str(path),
            chunks_total=len(chunks),
            chunks_new=len(ids),
            collection=self._collection,
            tags=tags,
        )

    def _extract_text(self, path: Path) -> str:
        reader = pypdf.PdfReader(str(path))
        return "\n".join(
            page.extract_text() or "" for page in reader.pages
        )

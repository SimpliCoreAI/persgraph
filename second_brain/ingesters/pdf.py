"""PDF ingester — extracts text, chunks, embeds, and stores."""

import hashlib
from datetime import datetime, timezone
from pathlib import Path
import re
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
        tags = self._auto_tags(path, tags, text)
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

        summary_note = self._summary_note(path, text, tags) if any(t in tags for t in ("college", "riverside", "school", "slides", "pdf", "screenshot")) else None
        return IngestResult(
            source=str(path),
            chunks_total=len(chunks),
            chunks_new=len(ids),
            collection=self._collection,
            tags=tags,
            doc_kind="pdf",
            summary_note=summary_note,
        )

    def _extract_text(self, path: Path) -> str:
        reader = pypdf.PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    def _auto_tags(self, path: Path, tags: list[str], text: str) -> list[str]:
        inferred = set(tags)
        blob = f"{path.name} {text[:5000]}".lower()
        for tag, needles in {
            "college": ["college", "orientation", "admissions", "campus", "enrollment", "riverside"],
            "riverside": ["riverside"],
            "school": ["school", "student", "parent", "teacher", "class", "district"],
            "slides": ["slide", "slides", "deck", "presentation"],
            "pdf": [".pdf", "pdf"],
            "screenshot": ["screenshot", "screen shot"],
        }.items():
            if any(n in blob for n in needles):
                inferred.add(tag)
        return sorted(inferred)

    def _summary_note(self, path: Path, text: str, tags: list[str]) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip()
        parts = re.split(r"(?<=[.!?])\s+", cleaned) if cleaned else []
        picks = []
        for part in parts:
            if any(k in part.lower() for k in ["date", "deadline", "contact", "email", "phone", "register", "signup", "orientation", "riverside", "college"]):
                picks.append(part.strip())
            if len(picks) >= 5:
                break
        if not picks:
            picks = parts[:3] if parts else ["No extractable text found."]
        return "\n".join([
            f"# Ingest summary: {path.name}",
            "",
            f"Source: {path}",
            f"Tags: {', '.join(tags) if tags else 'none'}",
            "",
            "## Key takeaways",
            *[f"- {p}" for p in picks],
        ])

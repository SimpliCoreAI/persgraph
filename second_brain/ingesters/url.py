"""URL ingester — scrapes web pages, chunks, embeds, and stores."""

import hashlib
from datetime import datetime, timezone
from urllib.parse import urlparse

import trafilatura

from ..config import settings
from ..embeddings import embedder
from ..vectorstore import vectorstore
from .base import BaseIngester, IngestResult


class URLIngester(BaseIngester):
    """Ingest web pages into the vector store."""

    def ingest(self, source: str, tags: list[str] | None = None) -> IngestResult:
        tags = tags or []

        if not self._is_valid_url(source):
            return IngestResult(
                source=source,
                chunks_total=0,
                chunks_new=0,
                collection=settings.collection_urls,
                tags=tags,
                errors=[f"Invalid URL: {source}"],
            )

        # Fetch and extract text
        text, title = self._fetch(source)
        if not text:
            return IngestResult(
                source=source,
                chunks_total=0,
                chunks_new=0,
                collection=settings.collection_urls,
                tags=tags,
                errors=[f"Could not extract content from: {source}"],
            )

        # Chunk
        chunks = self._chunk_text(text, settings.chunk_size, settings.chunk_overlap)
        url_hash = hashlib.md5(source.encode()).hexdigest()
        domain = urlparse(source).netloc

        # Skip already-ingested chunks
        collection = vectorstore.get_or_create(settings.collection_urls)
        existing_ids = set(collection.get()["ids"])

        ids, embeddings, documents, metadatas = [], [], [], []

        for i, chunk in enumerate(chunks):
            doc_id = f"{url_hash}_{i}"
            if doc_id in existing_ids:
                continue

            ids.append(doc_id)
            embeddings.append(embedder.embed(chunk))
            documents.append(chunk)
            metadatas.append({
                "source": source,
                "title": title or "",
                "domain": domain,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "tags": ",".join(tags),
            })

        if ids:
            vectorstore.upsert(
                collection_name=settings.collection_urls,
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )

        return IngestResult(
            source=source,
            chunks_total=len(chunks),
            chunks_new=len(ids),
            collection=settings.collection_urls,
            tags=tags,
        )

    def _fetch(self, url: str) -> tuple[str, str]:
        """Fetch URL and extract main content using trafilatura."""
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return "", ""

        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
        ) or ""

        # Extract title
        meta = trafilatura.extract_metadata(downloaded)
        title = meta.title if meta and meta.title else ""

        return text, title

    def _is_valid_url(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            return parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except Exception:
            return False

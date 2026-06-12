"""URL ingester — scrapes web pages, chunks, embeds, and stores."""

import hashlib
from datetime import datetime, timezone
from urllib.parse import urlparse

from ollama import ResponseError
from typing import Optional

import trafilatura

from ..config import settings
from ..embeddings import embedder
from ..vectorstore import vectorstore
from .base import BaseIngester, IngestResult


EMBED_SAFE_MAX_WORDS = 220
EMBED_SAFE_OVERLAP_WORDS = 32
EMBED_MIN_WORDS = 40


class URLIngester(BaseIngester):
    """Ingest web pages into the vector store."""

    def ingest(self, source: str, tags: Optional[list[str]] = None) -> IngestResult:
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

        # Chunk conservatively for embedding-model context safety.
        chunks = self._chunk_text(
            text,
            min(settings.chunk_size, EMBED_SAFE_MAX_WORDS),
            min(settings.chunk_overlap, EMBED_SAFE_OVERLAP_WORDS),
        )
        url_hash = hashlib.md5(source.encode()).hexdigest()
        domain = urlparse(source).netloc

        # Skip already-ingested chunks
        collection = vectorstore.get_or_create(settings.collection_urls)
        existing_ids = set(collection.get()["ids"])

        ids, documents, metadatas = [], [], []

        for i, chunk in enumerate(chunks):
            doc_id = f"{url_hash}_{i}"
            if doc_id in existing_ids:
                continue

            subchunks = self._split_for_embedding(chunk)
            for sub_index, subchunk in enumerate(subchunks):
                sub_id = doc_id if sub_index == 0 else f"{doc_id}_s{sub_index}"
                ids.append(sub_id)
                documents.append(subchunk)
                metadatas.append({
                    "source": source,
                    "title": title or "",
                    "domain": domain,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "ingested_at": datetime.now(timezone.utc).isoformat(),
                    "tags": ",".join(tags),
                    "source_type": self._detect_source_type(source, tags),
                    "subchunk_index": sub_index,
                    "subchunk_total": len(subchunks),
                })

        # Embed each chunk individually so a long article never becomes one oversized
        # batch payload at the embedding model boundary.
        embeddings = [embedder.embed(document) for document in documents] if documents else []

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

    def _split_for_embedding(self, document: str) -> list[str]:
        try:
            embedder.embed(document)
            return [document]
        except ResponseError as exc:
            message = str(exc).lower()
            if "context length" not in message:
                raise
            words = document.split()
            if len(words) <= EMBED_MIN_WORDS:
                raise ValueError(
                    "Chunk still exceeds embedding context even at minimum fallback size; "
                    f"document words={len(words)}"
                ) from exc
            mid = max(len(words) // 2, EMBED_MIN_WORDS)
            left = " ".join(words[:mid]).strip()
            right = " ".join(words[mid:]).strip()
            parts: list[str] = []
            if left:
                parts.extend(self._split_for_embedding(left))
            if right:
                parts.extend(self._split_for_embedding(right))
            return parts

    def _fetch(self, url: str) -> "tuple[str, str]":
        """Fetch URL and extract main content using trafilatura with browser headers."""
        import urllib.request

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }

        # Try trafilatura first
        downloaded = trafilatura.fetch_url(url)

        # Fallback: manual request with browser headers (handles some paywalls/bots)
        if not downloaded:
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    downloaded = resp.read().decode("utf-8", errors="replace")
            except Exception:
                return "", ""

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

    def _detect_source_type(self, url: str, tags: list[str]) -> str:
        """Infer source type from URL or tags."""
        if "medium" in tags or "medium.com" in url or "freedium" in url:
            return "medium"
        if "youtube.com" in url or "youtu.be" in url:
            return "youtube"
        if "substack.com" in url:
            return "substack"
        if "github.com" in url:
            return "github"
        if "pdf" in tags:
            return "pdf"
        return "web"

    def _is_valid_url(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            return parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except Exception:
            return False

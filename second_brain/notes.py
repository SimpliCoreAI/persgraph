"""
Notes / Tasks / Appointments — CRUD + semantic search via ChromaDB.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from .config import settings
from .embeddings import embedder
from .vectorstore import vectorstore

COLLECTION = "notes"

# Item types
TYPES = ["Task", "Appointment", "Note"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save(
    title: str,
    item_type: str = "Note",
    body: str = "",
    date: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    Save a note/task/appointment to ChromaDB.

    Returns the saved item dict.
    """
    tags = tags or []
    item_id = str(uuid4())

    # Text to embed — combine title + body for richer semantic search
    embed_text = f"{item_type}: {title}"
    if body:
        embed_text += f"\n{body}"

    embedding = embedder.embed(embed_text)

    metadata: dict[str, Any] = {
        "id": item_id,
        "type": item_type,
        "title": title,
        "body": body,
        "date": date or "",
        "tags": ",".join(tags),
        "created_at": _now(),
        "updated_at": _now(),
        "collection": COLLECTION,
    }

    vectorstore.upsert(
        collection_name=COLLECTION,
        ids=[item_id],
        embeddings=[embedding],
        documents=[embed_text],
        metadatas=[metadata],
    )

    return metadata


def search(query: str, top_k: int = 10) -> list[dict[str, Any]]:
    """Semantic search over notes collection."""
    embedding = embedder.embed(query)
    results = vectorstore.query(COLLECTION, embedding, top_k=top_k)
    return [_format(r) for r in results]


def list_all(
    item_type: Optional[str] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List notes, optionally filtered by type."""
    col = vectorstore.get(COLLECTION)
    if col is None or col.count() == 0:
        return []

    result = col.get(limit=limit, include=["metadatas"])
    items = result.get("metadatas", []) or []

    if item_type:
        items = [i for i in items if i.get("type") == item_type]

    # Sort by created_at descending
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return items


def delete(item_id: str) -> bool:
    """Delete a note by ID."""
    col = vectorstore.get(COLLECTION)
    if col is None:
        return False
    try:
        col.delete(ids=[item_id])
        return True
    except Exception:
        return False


def count() -> int:
    """Return total number of notes."""
    col = vectorstore.get(COLLECTION)
    return col.count() if col else 0


def _format(result: dict[str, Any]) -> dict[str, Any]:
    """Normalize a vectorstore result for display."""
    meta = result.get("metadata", {})
    return {
        **meta,
        "score": result.get("score", 0.0),
    }

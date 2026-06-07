"""
Travel & POI — CRUD + semantic search + auto-tagging via Qwen2.5.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from .config import settings
from .embeddings import embedder
from .llm import complete
from .vectorstore import vectorstore

COLLECTION = "places"
CATEGORIES = ["Restaurant", "Cafe", "Bar", "Hotel", "Market", "Landmark", "Park", "Shop", "Other"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def auto_tag(name: str, city: str, category: str, notes: str) -> list[str]:
    """
    Use Qwen2.5 to generate relevant tags for a place.
    Returns a list of 3-6 lowercase tags.
    """
    prompt = f"""Generate 3 to 6 short, relevant tags for this place.
Return ONLY a JSON array of lowercase strings. No explanation.

Place: {name}
City: {city}
Category: {category}
Notes: {notes}

Example output: ["indian", "biryani", "must-visit", "lunch"]

Tags:"""

    try:
        from .tracing import trace_event
        trace_event(
            name="places_auto_tag",
            input=f"place: {name}, city: {city}",
            tags=["places", "llm", "tagging"]
        )
        raw = complete(prompt, tier="fast").strip()

        # Extract JSON array from response
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start != -1 and end > start:
            tags = json.loads(raw[start:end])
            result = [str(t).lower().strip() for t in tags if t][:6]
            trace_event(
                name="places_auto_tag_result",
                output=f"tags: {', '.join(result)}",
                tags=["places", "llm", "tagging"]
            )
            return result
    except Exception:
        pass

    # Fallback: basic tags from category + city
    return [category.lower(), city.lower().split(",")[0].strip()]


def save(
    name: str,
    city: str,
    country: str = "",
    category: str = "Restaurant",
    notes: str = "",
    rating: Optional[int] = None,
    extra_tags: Optional[list[str]] = None,
    tags: Optional[list[str]] = None,  # if pre-computed, skip auto-tag
) -> dict[str, Any]:
    """Save a place to ChromaDB with auto-generated tags."""
    if tags is None:
        tags = auto_tag(name, city, category, notes)
    if extra_tags:
        tags = list(dict.fromkeys(tags + extra_tags))  # merge, dedupe

    place_id = str(uuid4())

    # Rich text for embedding — combines all fields for best semantic search
    location = f"{city}, {country}" if country else city
    embed_text = f"{category} in {location}: {name}. {notes}. Tags: {', '.join(tags)}"

    embedding = embedder.embed(embed_text)

    metadata: dict[str, Any] = {
        "id": place_id,
        "name": name,
        "city": city,
        "country": country,
        "category": category,
        "notes": notes,
        "rating": rating or 0,
        "tags": ",".join(tags),
        "created_at": _now(),
        "collection": COLLECTION,
    }

    vectorstore.upsert(
        collection_name=COLLECTION,
        ids=[place_id],
        embeddings=[embedding],
        documents=[embed_text],
        metadatas=[metadata],
    )

    return {**metadata, "tags_list": tags}


def search(query: str, top_k: int = 10, city: Optional[str] = None) -> list[dict[str, Any]]:
    """Semantic search over places, optionally filtered by city."""
    embedding = embedder.embed(query)
    results = vectorstore.query(COLLECTION, embedding, top_k=top_k * 2)

    if city:
        city_lower = city.lower().strip()
        results = [r for r in results if city_lower in r["metadata"].get("city", "").lower()]

    return [_format(r) for r in results[:top_k]]


def list_all(
    city: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """List all places, optionally filtered by city or category."""
    col = vectorstore.get(COLLECTION)
    if col is None or col.count() == 0:
        return []

    result = col.get(limit=limit, include=["metadatas"])
    items = result.get("metadatas", []) or []

    if city:
        items = [i for i in items if city.lower() in i.get("city", "").lower()]
    if category:
        items = [i for i in items if i.get("category", "") == category]

    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return items


def cities() -> list[str]:
    """Return sorted list of unique cities."""
    items = list_all()
    return sorted(set(i.get("city", "").strip() for i in items if i.get("city")))


def countries() -> list[str]:
    """Return sorted list of unique countries."""
    items = list_all()
    return sorted(set(i.get("country", "").strip() for i in items if i.get("country")))


def delete(place_id: str) -> bool:
    col = vectorstore.get(COLLECTION)
    if col is None:
        return False
    try:
        col.delete(ids=[place_id])
        return True
    except Exception:
        return False


def count() -> int:
    col = vectorstore.get(COLLECTION)
    return col.count() if col else 0


def _format(result: dict[str, Any]) -> dict[str, Any]:
    meta = result.get("metadata", {})
    return {**meta, "score": result.get("score", 0.0)}

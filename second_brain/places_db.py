"""
Places — SQLite-backed storage. No Ollama/ChromaDB dependency.

Replaces the ChromaDB places module for all save/list/search operations.
ChromaDB is still used for articles/notes; this is places-only.

DB file: data/places.db (local, always available)
"""

from __future__ import annotations

import json
import re
import sqlite3
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

DB_PATH = Path(__file__).parent.parent / "data" / "places.db"

CATEGORIES = [
    "Restaurant", "Cafe", "Bar", "Hotel", "Market",
    "Landmark", "Park", "Shop", "Other",
]


# ---------------------------------------------------------------------------
# DB bootstrap
# ---------------------------------------------------------------------------

def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS places (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            city        TEXT NOT NULL DEFAULT '',
            country     TEXT NOT NULL DEFAULT '',
            category    TEXT NOT NULL DEFAULT 'Restaurant',
            notes       TEXT NOT NULL DEFAULT '',
            rating      INTEGER,
            tags        TEXT NOT NULL DEFAULT '',
            maps_url    TEXT NOT NULL DEFAULT '',
            created_at  TEXT NOT NULL
        );

        -- Migration: add maps_url if upgrading from older schema
        CREATE TABLE IF NOT EXISTS _meta (key TEXT PRIMARY KEY, value TEXT);

        CREATE INDEX IF NOT EXISTS idx_places_city     ON places(city COLLATE NOCASE);
        CREATE INDEX IF NOT EXISTS idx_places_category ON places(category);
        CREATE INDEX IF NOT EXISTS idx_places_created  ON places(created_at DESC);

        CREATE VIRTUAL TABLE IF NOT EXISTS places_fts USING fts5(
            name, city, country, category, notes, tags,
            content='places', content_rowid='rowid',
            tokenize='unicode61 remove_diacritics 2'
        );

        CREATE TRIGGER IF NOT EXISTS places_ai AFTER INSERT ON places BEGIN
            INSERT INTO places_fts(rowid, name, city, country, category, notes, tags)
            VALUES (new.rowid, new.name, new.city, new.country, new.category, new.notes, new.tags);
        END;

        CREATE TRIGGER IF NOT EXISTS places_ad AFTER DELETE ON places BEGIN
            INSERT INTO places_fts(places_fts, rowid, name, city, country, category, notes, tags)
            VALUES ('delete', old.rowid, old.name, old.city, old.country, old.category, old.notes, old.tags);
        END;

        CREATE TRIGGER IF NOT EXISTS places_au AFTER UPDATE ON places BEGIN
            INSERT INTO places_fts(places_fts, rowid, name, city, country, category, notes, tags)
            VALUES ('delete', old.rowid, old.name, old.city, old.country, old.category, old.notes, old.tags);
            INSERT INTO places_fts(rowid, name, city, country, category, notes, tags)
            VALUES (new.rowid, new.name, new.city, new.country, new.category, new.notes, new.tags);
        END;
    """)
    # Migration: add maps_url column if it doesn't exist yet
    cols = {r[1] for r in conn.execute("PRAGMA table_info(places)").fetchall()}
    if "maps_url" not in cols:
        conn.execute("ALTER TABLE places ADD COLUMN maps_url TEXT NOT NULL DEFAULT ''")
        conn.commit()
    conn.commit()


def _maps_url(name: str, city: str, country: str = "") -> str:
    """Build a Google Maps search URL from place name + location."""
    parts = [p for p in [name, city, country] if p]
    query = urllib.parse.quote_plus(" ".join(parts))
    return f"https://www.google.com/maps/search/?api=1&query={query}"


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["tags_list"] = [t.strip() for t in d.get("tags", "").split(",") if t.strip()]
    return d


# Common city abbreviations
_CITY_ALIASES: dict[str, str] = {
    "sf": "San Francisco",
    "nyc": "New York",
    "ny": "New York",
    "la": "Los Angeles",
    "dc": "Washington",
    "chi": "Chicago",
    "phx": "Phoenix",
    "sea": "Seattle",
    "pdx": "Portland",
    "atl": "Atlanta",
    "bos": "Boston",
    "mia": "Miami",
    "dal": "Dallas",
    "hou": "Houston",
    "den": "Denver",
    "lv": "Las Vegas",
    "sd": "San Diego",
    "sj": "San Jose",
}


def _expand_city(query: str) -> str:
    """Expand common city abbreviations."""
    return _CITY_ALIASES.get(query.lower().strip(), query)


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def save(
    name: str,
    city: str,
    country: str = "",
    category: str = "Restaurant",
    notes: str = "",
    rating: Optional[int] = None,
    tags: Optional[list[str]] = None,
    extra_tags: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Save a place. Returns the saved record."""
    if tags is None:
        # Basic auto-tags from category + city — no LLM needed
        tags = _basic_tags(name, city, category)
    if extra_tags:
        tags = list(dict.fromkeys(tags + extra_tags))

    place_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    tags_str = ",".join(tags)
    url = _maps_url(name, city, country)

    with _conn() as conn:
        conn.execute(
            """INSERT INTO places (id, name, city, country, category, notes, rating, tags, maps_url, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (place_id, name.strip(), city.strip(), country.strip(),
             category, notes.strip(), rating, tags_str, url, now),
        )

    return {
        "id": place_id, "name": name, "city": city, "country": country,
        "category": category, "notes": notes, "rating": rating,
        "tags": tags_str, "tags_list": tags, "maps_url": url, "created_at": now,
    }


def delete(place_id: str) -> bool:
    with _conn() as conn:
        cur = conn.execute("DELETE FROM places WHERE id = ?", (place_id,))
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def list_all(
    city: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """List all places, optionally filtered by city/category."""
    sql = "SELECT * FROM places"
    params: list[Any] = []
    clauses: list[str] = []

    if city:
        clauses.append("city LIKE ?")
        params.append(f"%{city}%")
    if category:
        clauses.append("category = ?")
        params.append(category)

    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with _conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def search(query: str, city: Optional[str] = None, top_k: int = 15) -> list[dict[str, Any]]:
    """Full-text search over places using SQLite FTS5."""
    # Expand city abbreviations
    query = _expand_city(query)
    if city:
        city = _expand_city(city)
    # Sanitize query for FTS5
    safe_q = re.sub(r'[^\w\s]', ' ', query).strip()
    if not safe_q:
        return list_all(city=city, limit=top_k)

    sql = """
        SELECT p.* FROM places p
        JOIN places_fts f ON p.rowid = f.rowid
        WHERE places_fts MATCH ?
        ORDER BY rank
        LIMIT ?
    """
    params: list[Any] = [safe_q + "*", top_k * 2]

    with _conn() as conn:
        try:
            rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            # FTS fallback: simple LIKE
            rows = conn.execute(
                "SELECT * FROM places WHERE name LIKE ? OR notes LIKE ? OR tags LIKE ? LIMIT ?",
                (f"%{query}%", f"%{query}%", f"%{query}%", top_k),
            ).fetchall()

    results = [_row_to_dict(r) for r in rows]
    if city:
        results = [r for r in results if city.lower() in r.get("city", "").lower()]
    return results[:top_k]


def get_by_id(place_id: str) -> Optional[dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM places WHERE id = ?", (place_id,)).fetchone()
    return _row_to_dict(row) if row else None


def cities() -> list[str]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT city FROM places WHERE city != '' ORDER BY city"
        ).fetchall()
    return [r["city"] for r in rows]


def count() -> int:
    with _conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM places").fetchone()[0]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _basic_tags(name: str, city: str, category: str) -> list[str]:
    """Generate basic tags without LLM — category + city slug."""
    tags = [category.lower()]
    city_slug = city.lower().split(",")[0].strip().replace(" ", "-")
    if city_slug:
        tags.append(city_slug)
    # Add "pizza" / "coffee" etc from name if obvious
    name_lower = name.lower()
    for keyword in ["pizza", "sushi", "tacos", "ramen", "burger", "coffee", "tea", "bbq", "vegan"]:
        if keyword in name_lower:
            tags.append(keyword)
            break
    return tags


# ---------------------------------------------------------------------------
# Bulk import (for migration)
# ---------------------------------------------------------------------------

def bulk_import(records: list[dict[str, Any]]) -> int:
    """Import a list of place dicts (e.g. from ChromaDB export). Returns count saved."""
    saved = 0
    for r in records:
        try:
            tags = r.get("tags", "")
            tags_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
            save(
                name=r.get("name", "Unknown"),
                city=r.get("city", ""),
                country=r.get("country", ""),
                category=r.get("category", "Restaurant"),
                notes=r.get("notes", ""),
                rating=r.get("rating") or None,
                tags=tags_list,
            )
            saved += 1
        except Exception:
            pass
    return saved

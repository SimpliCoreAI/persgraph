"""
Notes / Tasks / Appointments — SQLite-backed storage. No Ollama/ChromaDB dependency.

Replaces ChromaDB notes module for all save/list/search operations.
DB file: data/notes.db (local, always available)

API matches second_brain.notes exactly so all callers work without changes.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

DB_PATH = Path(__file__).parent.parent / "data" / "notes.db"

# Item types — same as original
TYPES = ["Task", "Appointment", "Note"]


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
        CREATE TABLE IF NOT EXISTS notes (
            id          TEXT PRIMARY KEY,
            type        TEXT NOT NULL DEFAULT 'Note',
            title       TEXT NOT NULL,
            body        TEXT NOT NULL DEFAULT '',
            date        TEXT NOT NULL DEFAULT '',
            tags        TEXT NOT NULL DEFAULT '',
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_notes_type    ON notes(type);
        CREATE INDEX IF NOT EXISTS idx_notes_date    ON notes(date);
        CREATE INDEX IF NOT EXISTS idx_notes_created ON notes(created_at DESC);

        CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
            title, body, tags, type,
            content='notes', content_rowid='rowid',
            tokenize='unicode61 remove_diacritics 2'
        );

        CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
            INSERT INTO notes_fts(rowid, title, body, tags, type)
            VALUES (new.rowid, new.title, new.body, new.tags, new.type);
        END;

        CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
            INSERT INTO notes_fts(notes_fts, rowid, title, body, tags, type)
            VALUES ('delete', old.rowid, old.title, old.body, old.tags, old.type);
        END;

        CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
            INSERT INTO notes_fts(notes_fts, rowid, title, body, tags, type)
            VALUES ('delete', old.rowid, old.title, old.body, old.tags, old.type);
            INSERT INTO notes_fts(rowid, title, body, tags, type)
            VALUES (new.rowid, new.title, new.body, new.tags, new.type);
        END;
    """)
    conn.commit()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    # Normalize tags to list for callers that expect it
    d["tags_list"] = [t.strip() for t in d.get("tags", "").split(",") if t.strip()]
    return d


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def save(
    title: str,
    item_type: str = "Note",
    body: str = "",
    date: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    Save a note/task/appointment to SQLite.
    Returns the saved item dict (same shape as the ChromaDB version).
    """
    tags = tags or []
    item_id = str(uuid4())
    now = _now()
    tags_str = ",".join(tags)
    date_str = date or ""

    with _conn() as conn:
        conn.execute(
            """INSERT INTO notes (id, type, title, body, date, tags, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (item_id, item_type, title.strip(), body.strip(), date_str, tags_str, now, now),
        )

    return {
        "id": item_id,
        "type": item_type,
        "title": title,
        "body": body,
        "date": date_str,
        "tags": tags_str,
        "created_at": now,
        "updated_at": now,
        "collection": "notes",  # kept for backward compat
    }


def delete(item_id: str) -> bool:
    """Delete a note by ID."""
    with _conn() as conn:
        cur = conn.execute("DELETE FROM notes WHERE id = ?", (item_id,))
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def list_all(
    item_type: Optional[str] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List notes, optionally filtered by type. Same signature as ChromaDB version."""
    sql = "SELECT * FROM notes"
    params: list[Any] = []

    if item_type:
        sql += " WHERE type = ?"
        params.append(item_type)

    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with _conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def search(query: str, top_k: int = 10) -> list[dict[str, Any]]:
    """Full-text search over notes using SQLite FTS5."""
    safe_q = re.sub(r'[^\w\s]', ' ', query).strip()
    if not safe_q:
        return list_all(limit=top_k)

    sql = """
        SELECT n.* FROM notes n
        JOIN notes_fts f ON n.rowid = f.rowid
        WHERE notes_fts MATCH ?
        ORDER BY rank
        LIMIT ?
    """
    with _conn() as conn:
        try:
            rows = conn.execute(sql, [safe_q + "*", top_k]).fetchall()
        except sqlite3.OperationalError:
            # FTS fallback: simple LIKE
            rows = conn.execute(
                "SELECT * FROM notes WHERE title LIKE ? OR body LIKE ? OR tags LIKE ? LIMIT ?",
                (f"%{query}%", f"%{query}%", f"%{query}%", top_k),
            ).fetchall()

    # Add a synthetic score field to match the ChromaDB result shape
    results = [_row_to_dict(r) for r in rows]
    for r in results:
        r.setdefault("score", 1.0)
    return results


def get_by_id(item_id: str) -> Optional[dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM notes WHERE id = ?", (item_id,)).fetchone()
    return _row_to_dict(row) if row else None


def count() -> int:
    with _conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]


# ---------------------------------------------------------------------------
# Bulk import (migration helper from ChromaDB export)
# ---------------------------------------------------------------------------

def bulk_import(records: list[dict[str, Any]]) -> int:
    """Import a list of note dicts (e.g. from ChromaDB export). Returns count saved."""
    saved = 0
    for r in records:
        try:
            tags_raw = r.get("tags", "")
            tags_list = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []
            save(
                title=r.get("title", "Untitled"),
                item_type=r.get("type", "Note"),
                body=r.get("body", ""),
                date=r.get("date") or None,
                tags=tags_list,
            )
            saved += 1
        except Exception:
            pass
    return saved

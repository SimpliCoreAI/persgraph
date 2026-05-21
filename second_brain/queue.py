"""
Async save queue — write items instantly, process in background.

Supports: places, notes, urls, pdfs
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

QUEUE_FILE = Path(__file__).parent.parent / "data" / "queue.json"

VALID_TYPES = {"place", "note", "task", "appointment", "url", "pdf"}
STATUS_PENDING = "pending"
STATUS_DONE = "done"
STATUS_FAILED = "failed"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> list[dict]:
    if QUEUE_FILE.exists():
        with open(QUEUE_FILE) as f:
            return json.load(f)
    return []


def _save(items: list[dict]) -> None:
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(QUEUE_FILE, "w") as f:
        json.dump(items, f, indent=2)


def enqueue(item_type: str, payload: dict[str, Any]) -> dict:
    """Add an item to the queue. Returns the queued item."""
    if item_type not in VALID_TYPES:
        raise ValueError(f"Unknown type: {item_type}. Valid: {VALID_TYPES}")

    item = {
        "id": str(uuid.uuid4()),
        "type": item_type,
        "payload": payload,
        "status": STATUS_PENDING,
        "queued_at": _now(),
        "processed_at": None,
        "error": None,
    }

    items = _load()
    items.append(item)
    _save(items)
    return item


def pending() -> list[dict]:
    """Return all pending items."""
    return [i for i in _load() if i["status"] == STATUS_PENDING]


def mark_done(item_id: str) -> None:
    items = _load()
    for item in items:
        if item["id"] == item_id:
            item["status"] = STATUS_DONE
            item["processed_at"] = _now()
    _save(items)


def mark_failed(item_id: str, error: str) -> None:
    items = _load()
    for item in items:
        if item["id"] == item_id:
            item["status"] = STATUS_FAILED
            item["error"] = error
            item["processed_at"] = _now()
    _save(items)


def stats() -> dict:
    items = _load()
    return {
        "total": len(items),
        "pending": sum(1 for i in items if i["status"] == STATUS_PENDING),
        "done": sum(1 for i in items if i["status"] == STATUS_DONE),
        "failed": sum(1 for i in items if i["status"] == STATUS_FAILED),
    }

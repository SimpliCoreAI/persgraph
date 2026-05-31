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
STATUS_RETRY = "pending_retry"   # saved ok, waiting for dependency (e.g. Windows) to come back
STATUS_DONE = "done"
STATUS_FAILED = "failed"

# Dependencies that can block processing
DEP_CHROMADB = "chromadb"
DEP_OLLAMA = "ollama"


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
    """Return all pending items (excludes pending_retry — use pending_retry() for those)."""
    return [i for i in _load() if i["status"] == STATUS_PENDING]


def pending_retry(deps: list[str] | None = None) -> list[dict]:
    """
    Return items waiting for a dependency to come back.
    If deps given, filter to items that need any of those deps.
    """
    items = [i for i in _load() if i["status"] == STATUS_RETRY]
    if deps:
        items = [
            i for i in items
            if any(d in i.get("retry_needs", []) for d in deps)
        ]
    return items


def enqueue_retry(item_type: str, payload: dict[str, Any], needs: list[str]) -> dict:
    """
    Queue an item that can't be processed right now due to missing deps.
    `needs` is a list of dep strings e.g. [DEP_CHROMADB].
    """
    if item_type not in VALID_TYPES:
        raise ValueError(f"Unknown type: {item_type}. Valid: {VALID_TYPES}")

    item = {
        "id": str(uuid.uuid4()),
        "type": item_type,
        "payload": payload,
        "status": STATUS_RETRY,
        "retry_needs": needs,
        "queued_at": _now(),
        "processed_at": None,
        "error": None,
    }

    items = _load()
    items.append(item)
    _save(items)
    return item


def mark_retry_pending(item_id: str) -> None:
    """Promote a pending_retry item back to pending so the worker picks it up."""
    items = _load()
    for item in items:
        if item["id"] == item_id and item["status"] == STATUS_RETRY:
            item["status"] = STATUS_PENDING
            item.pop("retry_needs", None)
    _save(items)


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
        "pending_retry": sum(1 for i in items if i["status"] == STATUS_RETRY),
        "done": sum(1 for i in items if i["status"] == STATUS_DONE),
        "failed": sum(1 for i in items if i["status"] == STATUS_FAILED),
    }

#!/usr/bin/env python3
"""
Queue worker — processes pending items from data/queue.json.
Embeds + saves to ChromaDB, then reports results.

Called by OpenClaw cron every 90 minutes.
Output is used by OpenClaw to send Telegram confirmations.

Also drains pending_retry items when their required dependency is reachable.
"""

import sys
import os
import json
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from second_brain.queue import (
    pending, mark_done, mark_failed, mark_retry_pending,
    pending_retry, stats, DEP_CHROMADB, DEP_OLLAMA,
)


def process_place(payload: dict) -> str:
    from second_brain.places_db import save  # SQLite — no Ollama/ChromaDB needed
    result = save(
        name=payload["name"],
        city=payload.get("city", ""),
        country=payload.get("country", ""),
        category=payload.get("category", "Restaurant"),
        notes=payload.get("notes", ""),
        rating=payload.get("rating"),
        extra_tags=payload.get("extra_tags", []),
        tags=payload.get("tags"),  # if pre-tagged, skip auto-tag
    )
    tags = result.get("tags_list") or result.get("tags", "").split(",")
    city_country = ", ".join(filter(None, [result.get("city"), result.get("country")]))
    return f"📍 {result['name']} · {city_country} · tags: {', '.join(tags)}"


def process_note(payload: dict) -> str:
    from second_brain.notes import save
    result = save(
        title=payload["title"],
        item_type=payload.get("type", "Note"),
        body=payload.get("body", ""),
        date=payload.get("date", ""),
        tags=payload.get("tags", "").split(",") if isinstance(payload.get("tags"), str) else payload.get("tags", []),
    )
    return f"✅ [{result['type']}] {result['title']}"


def process_url(payload: dict) -> str:
    from second_brain.ingesters.url import URLIngester
    result = URLIngester().ingest(
        payload["url"],
        tags=payload.get("tags", []),
    )
    if result.success:
        return f"🌐 {payload['url']} · {result.chunks_new} chunks ingested"
    else:
        raise Exception(", ".join(result.errors))


PROCESSORS = {
    "place":       process_place,
    "note":        process_note,
    "task":        process_note,
    "appointment": process_note,
    "url":         process_url,
}


def promote_retry_items() -> int:
    """
    Check which pending_retry items can now be processed (dependency is back online).
    Promote them to 'pending' so the main loop picks them up.
    Returns number of items promoted.
    """
    from second_brain.connectivity import chromadb_reachable, ollama_reachable, bust_cache
    bust_cache()  # fresh probe, ignore cached result

    promoted = 0
    chroma_up = chromadb_reachable()
    ollama_up = ollama_reachable()

    retry_items = pending_retry()
    for item in retry_items:
        needs = item.get("retry_needs", [])
        can_run = True
        for dep in needs:
            if dep == DEP_CHROMADB and not chroma_up:
                can_run = False
            elif dep == DEP_OLLAMA and not ollama_up:
                can_run = False
        if can_run:
            mark_retry_pending(item["id"])
            promoted += 1

    return promoted


# Item types that require ChromaDB/Ollama on Windows machine
CHROMA_DEPENDENT_TYPES = {"url", "pdf", "note", "task", "appointment"}


def run() -> list[dict]:
    """Process all pending items. Returns list of results."""
    # ── Langfuse trace setup ──────────────────────────────────────────────────
    _lf_trace = None
    _lf = None
    _lf_start = time.perf_counter()
    try:
        from second_brain.config import settings as _s
        import os as _os
        _os.environ.setdefault("LANGFUSE_SECRET_KEY", _s.langfuse_secret_key)
        _os.environ.setdefault("LANGFUSE_PUBLIC_KEY", _s.langfuse_public_key)
        _os.environ.setdefault("LANGFUSE_HOST", _s.langfuse_host)
        if _s.langfuse_secret_key:
            from langfuse import Langfuse
            _lf = Langfuse(secret_key=_s.langfuse_secret_key, public_key=_s.langfuse_public_key, host=_s.langfuse_host)
            _lf_trace = _lf.trace(name="queue-worker", tags=["second-brain", "queue-worker"])
    except Exception:
        pass
    # ───────────────────────────────────────────────────────────────────

    # First: promote any retry items whose deps are now available
    promoted = promote_retry_items()

    items = pending()
    if not items:
        return [{"promoted": promoted}] if promoted else []

    # Check ChromaDB once (already cached from promote_retry_items probe)
    from second_brain.connectivity import chromadb_reachable
    chroma_up = chromadb_reachable()

    results = []
    for item in items:
        item_type = item["type"]
        processor = PROCESSORS.get(item_type)

        if not processor:
            mark_failed(item["id"], f"No processor for type: {item_type}")
            results.append({"id": item["id"], "status": "failed", "message": f"Unknown type: {item_type}"})
            continue

        # Skip ChromaDB-dependent items if Windows is offline — move to retry queue
        if item_type in CHROMA_DEPENDENT_TYPES and not chroma_up:
            from second_brain.queue import enqueue_retry, DEP_CHROMADB, _load, _save, STATUS_RETRY
            items_all = _load()
            for i in items_all:
                if i["id"] == item["id"]:
                    i["status"] = STATUS_RETRY
                    i["retry_needs"] = [DEP_CHROMADB]
            _save(items_all)
            results.append({"id": item["id"], "status": "skipped", "message": f"Deferred: Windows offline"})
            continue

        try:
            message = processor(item["payload"])
            mark_done(item["id"])
            results.append({"id": item["id"], "status": "done", "message": message})
            # Langfuse span per processed item
            if _lf_trace:
                try:
                    _lf_trace.span(
                        name=f"process-{item_type}",
                        input=str(item.get("payload", ""))[:300],
                        output=message[:300],
                        metadata={"item_type": item_type},
                    )
                except Exception:
                    pass
        except Exception as e:
            err = str(e)
            mark_failed(item["id"], err)
            results.append({"id": item["id"], "status": "failed", "message": err})

    # ── Langfuse: close trace ───────────────────────────────────────────────
    if _lf_trace and _lf:
        try:
            done_n = sum(1 for r in results if r.get("status") == "done")
            failed_n = sum(1 for r in results if r.get("status") == "failed")
            _lf_trace.update(
                output=f"{done_n} done, {failed_n} failed, {len(results)} total",
                metadata={"latency_ms": int((time.perf_counter() - _lf_start) * 1000)},
            )
            _lf.flush()
        except Exception:
            pass
    # ───────────────────────────────────────────────────────────────────

    return results


if __name__ == "__main__":
    results = run()

    # Filter out the internal promoted-count sentinel
    promoted_count = next((r["promoted"] for r in results if "promoted" in r), 0)
    real_results = [r for r in results if "promoted" not in r]

    if not real_results and not promoted_count:
        # Also report how many items are still waiting
        from second_brain.queue import pending_retry
        waiting = len(pending_retry())
        if waiting:
            print(f"QUEUE_EMPTY (but {waiting} item(s) waiting for Windows to come back online)")
        else:
            print("QUEUE_EMPTY")
        sys.exit(0)

    # Print summary for OpenClaw to parse and send to Telegram
    done = [r for r in real_results if r["status"] == "done"]
    failed = [r for r in real_results if r["status"] == "failed"]

    summary_parts = []
    if done or failed:
        summary_parts.append(f"{len(done)} saved, {len(failed)} failed")
    if promoted_count and not real_results:
        summary_parts.append(f"{promoted_count} item(s) unlocked (Windows back online) — processing now")

    print(f"QUEUE_PROCESSED: {', '.join(summary_parts) or 'ok'}")
    print()
    for r in done:
        print(f"✅ {r['message']}")
    for r in failed:
        print(f"❌ {r['message']}")

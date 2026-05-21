#!/usr/bin/env python3
"""
Queue worker — processes pending items from data/queue.json.
Embeds + saves to ChromaDB, then reports results.

Called by OpenClaw cron every 30 minutes.
Output is used by OpenClaw to send Telegram confirmations.
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from second_brain.queue import pending, mark_done, mark_failed, stats


def process_place(payload: dict) -> str:
    from second_brain.places import save
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
    return f"📍 {result['name']} · {result['city']}, {result['country']} · tags: {', '.join(tags)}"


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


def run() -> list[dict]:
    """Process all pending items. Returns list of results."""
    items = pending()
    if not items:
        return []

    results = []
    for item in items:
        item_type = item["type"]
        processor = PROCESSORS.get(item_type)

        if not processor:
            mark_failed(item["id"], f"No processor for type: {item_type}")
            results.append({"id": item["id"], "status": "failed", "message": f"Unknown type: {item_type}"})
            continue

        try:
            message = processor(item["payload"])
            mark_done(item["id"])
            results.append({"id": item["id"], "status": "done", "message": message})
        except Exception as e:
            err = str(e)
            mark_failed(item["id"], err)
            results.append({"id": item["id"], "status": "failed", "message": err})

    return results


if __name__ == "__main__":
    results = run()

    if not results:
        print("QUEUE_EMPTY")
        sys.exit(0)

    # Print summary for OpenClaw to parse and send to Telegram
    done = [r for r in results if r["status"] == "done"]
    failed = [r for r in results if r["status"] == "failed"]

    print(f"QUEUE_PROCESSED: {len(done)} saved, {len(failed)} failed")
    print()
    for r in done:
        print(f"✅ {r['message']}")
    for r in failed:
        print(f"❌ {r['message']}")

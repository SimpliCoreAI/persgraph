#!/usr/bin/env python3
"""
migrate_places.py — One-time migration: ChromaDB places → SQLite places.db

Run this ONCE when your Windows machine (Tailscale IP from config.yaml) is reachable:
    cd ~/AgenticHub/Persgraph && PYTHONPATH=. .venv/bin/python scripts/migrate_places.py

Will not re-import already-existing records (skips duplicates by name+city).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def fetch_from_chroma() -> list[dict]:
    """Pull all places from ChromaDB."""
    from second_brain.vectorstore import vectorstore
    col = vectorstore.get("places")
    if col is None or col.count() == 0:
        print("⚠️  No 'places' collection in ChromaDB (or empty).")
        return []
    result = col.get(limit=1000, include=["metadatas"])
    items = result.get("metadatas", []) or []
    print(f"📦 Found {len(items)} places in ChromaDB")
    return items


def run():
    print("🔄 Starting places migration: ChromaDB → SQLite\n")

    records = fetch_from_chroma()
    if not records:
        print("Nothing to migrate.")
        return

    from second_brain.places_db import bulk_import, list_all, count as total_count

    before = total_count()
    saved = bulk_import(records)
    after = total_count()

    print(f"\n✅ Migration complete!")
    print(f"   Records in ChromaDB : {len(records)}")
    print(f"   Saved to SQLite     : {saved}")
    print(f"   SQLite total now    : {after} (was {before})")

    # Show a sample
    print("\n📋 Sample (first 5):")
    for p in list_all(limit=5):
        print(f"  • {p['name']}, {p['city']} [{p['category']}]")


if __name__ == "__main__":
    run()

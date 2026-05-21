#!/usr/bin/env python3
"""
Ingest CC rewards PDFs into ChromaDB.
Reads cards.json, finds PDFs in data/cc_rewards/, ingests each one.
Deletes PDF after successful ingestion.

Usage:
    python scripts/ingest_cc_rewards.py           # ingest all pending PDFs
    python scripts/ingest_cc_rewards.py --dry-run # show what would be ingested
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from second_brain.ingesters.pdf import PDFIngester

CARDS_FILE = Path(__file__).parent.parent / "data" / "cards.json"
CC_REWARDS_DIR = Path(__file__).parent.parent / "data" / "cc_rewards"
COLLECTION = "cc_rewards"


def load_cards() -> list[dict]:
    if not CARDS_FILE.exists():
        return []
    with open(CARDS_FILE) as f:
        return json.load(f)


def ingest_all(dry_run: bool = False) -> None:
    cards = load_cards()
    card_map = {c["id"]: c for c in cards}

    # Find all PDFs in cc_rewards/
    pdfs = list(CC_REWARDS_DIR.glob("*.pdf"))

    if not pdfs:
        print("No PDFs found in data/cc_rewards/")
        return

    ingester = PDFIngester(collection_override=COLLECTION)

    for pdf_path in pdfs:
        # Match PDF to card by filename stem (e.g. card_1.pdf → card_1)
        card_id = pdf_path.stem
        card = card_map.get(card_id)
        card_name = card["name"] if card else card_id

        print(f"\n📄 {pdf_path.name} → [{card_name}]")

        if dry_run:
            print(f"   [DRY RUN] Would ingest as: {COLLECTION}, tags: [{card_id}, {card['issuer'] if card else ''}]")
            continue

        tags = [card_id]
        if card:
            tags += [card["issuer"].lower(), card["rewards_type"], card["name"].lower().replace(" ", "-")]

        result = ingester.ingest(str(pdf_path), tags=tags)

        if result.success:
            print(f"   ✅ {result.chunks_new} new chunks ingested")
            # Delete PDF after successful ingestion
            pdf_path.unlink()
            print(f"   🗑️  Deleted {pdf_path.name}")
        else:
            print(f"   ❌ Failed: {result.errors}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest CC rewards PDFs")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be ingested without doing it")
    args = parser.parse_args()

    ingest_all(dry_run=args.dry_run)

#!/usr/bin/env python3
"""
Second Brain — Slash Command Handler

Handles commands sent from Telegram via OpenClaw:
  /ingest <url>              — ingest a URL into the brain
  /ask <question>            — query the brain
  /note <text>               — save a quick note
  /task <text>               — save a task
  /place <name>, <city>      — save a place
  /status                    — show queue + collection stats

Usage:
    python scripts/command.py "/ingest https://example.com"
    python scripts/command.py "/ask what is RAG?"
    python scripts/command.py "/note buy groceries"
    python scripts/command.py "/status"
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def cmd_ingest(args: str) -> str:
    url = args.strip()
    if not url:
        return "❌ Usage: /ingest <url>"

    # Auto-apply Freedium for Medium URLs
    if "medium.com" in url and "freedium" not in url:
        url = f"https://freedium-mirror.cfd/{url}"

    from second_brain.ingesters.url import URLIngester

    # Auto-detect tags
    tags = []
    if "medium.com" in args or "freedium" in url:
        tags.append("medium")
    if "youtube.com" in args or "youtu.be" in args:
        tags.append("youtube")
    if "github.com" in args:
        tags.append("github")

    result = URLIngester().ingest(url, tags=tags)
    if result.success:
        return (
            f"✅ Ingested!\n"
            f"📦 Collection: {result.collection}\n"
            f"✂️ Chunks: {result.chunks_new} new / {result.chunks_total} total\n"
            f"🏷️ Tags: {', '.join(result.tags) or 'none'}"
        )
    else:
        return f"❌ Ingestion failed: {'; '.join(result.errors)}"


def cmd_ask(question: str) -> str:
    """Retrieve relevant chunks from the brain. Claude synthesizes the answer."""
    if not question.strip():
        return "❌ Usage: /ask <question>"

    from second_brain.embeddings import embedder
    from second_brain.vectorstore import vectorstore

    # Embed the question
    q_vec = embedder.embed(question)

    # Query all collections
    results = vectorstore.query_all(q_vec, top_k=5)
    if not results:
        return "🤷 Nothing relevant found in the brain yet. Try /ingest some articles first!"

    # Return structured context for Claude to synthesize
    output_lines = [f"📖 Retrieved {len(results)} chunks for: \"{question}\"\n"]
    for i, r in enumerate(results, 1):
        meta = r.get("metadata", {})
        title = meta.get("title", "Unknown source")
        source_type = meta.get("source_type", "web")
        score = r.get("score", 0)
        output_lines.append(f"[{i}] {title} ({source_type}, score={score})")
        output_lines.append(r['text'].strip())
        output_lines.append("")

    return "\n".join(output_lines)


def cmd_wiki_ingest(args: str) -> str:
    """
    Step 1 of /wiki-ingest: ingest to ChromaDB and return raw chunks.
    The agent (Claude via OpenClaw) handles synthesis + writes the Obsidian note.
    """
    url = args.strip()
    if not url:
        return "❌ Usage: /wiki-ingest <url>"

    # Auto-apply Freedium for Medium
    fetch_url = url
    tags = []
    if "medium.com" in url and "freedium" not in url:
        fetch_url = f"https://freedium-mirror.cfd/{url}"
        tags.append("medium")
    if "youtube.com" in url or "youtu.be" in url:
        tags.append("youtube")
    if "github.com" in url:
        tags.append("github")

    from second_brain.ingesters.url import URLIngester
    from second_brain.embeddings import embedder
    from second_brain.vectorstore import vectorstore
    from second_brain.config import settings
    import trafilatura

    # Ingest to ChromaDB
    result = URLIngester().ingest(fetch_url, tags=tags)
    if not result.success:
        return f"❌ Ingestion failed: {'; '.join(result.errors)}"

    # Fetch title
    title = ""
    try:
        downloaded = trafilatura.fetch_url(fetch_url)
        if downloaded:
            meta = trafilatura.extract_metadata(downloaded)
            title = meta.title if meta and meta.title else ""
    except Exception:
        pass
    title = title or url

    # Retrieve chunks for this specific URL only
    import hashlib
    url_hash = hashlib.md5(fetch_url.encode()).hexdigest()
    collection = vectorstore.get_or_create(result.collection)
    all_docs = collection.get(where={"source": fetch_url}) if fetch_url else None

    # Fallback: hash-based ID prefix filter
    if not all_docs or not all_docs.get("documents"):
        all_ids = collection.get()["ids"]
        matching_ids = [i for i in all_ids if i.startswith(url_hash)]
        if matching_ids:
            all_docs = collection.get(ids=matching_ids)

    chunk_texts = all_docs["documents"] if all_docs and all_docs.get("documents") else []
    combined = "\n\n---\n\n".join(chunk_texts)

    # Quality gate — catch thin/junk articles before synthesis
    total_chars = sum(len(t) for t in chunk_texts)
    quality_warnings = []

    if len(chunk_texts) < 3:
        quality_warnings.append(f"⚠️ Only {len(chunk_texts)} chunks extracted — article may be paywalled or very short")
    if total_chars < 1500:
        quality_warnings.append(f"⚠️ Low content volume ({total_chars} chars) — may be a stub or blocked page")
    if any(w in combined.lower() for w in ["referral", "affiliate", "promo code", "sign up and get", "use my link"]):
        quality_warnings.append("⚠️ Affiliate/promo content detected — signal-to-noise may be low")

    warnings_str = "\n".join(quality_warnings)
    quality_block = f"\n{warnings_str}" if quality_warnings else ""

    return (
        f"WIKI_INGEST_READY\n"
        f"title: {title}\n"
        f"source_url: {url}\n"
        f"chunks_new: {result.chunks_new}\n"
        f"chunks_total: {result.chunks_total}\n"
        f"content_chars: {total_chars}\n"
        f"quality_warnings: {len(quality_warnings)}{quality_block}\n"
        f"vault_path: {settings.obsidian_vault_path}\n"
        f"---CHUNKS---\n"
        f"{combined}"
    )


def cmd_note(text: str) -> str:
    if not text.strip():
        return "❌ Usage: /note <text>"
    from second_brain.queue import enqueue
    item = enqueue("note", {"title": text[:80], "body": text, "type": "Note", "tags": ["note", "quick-capture"]})
    return f"✅ Note queued! Will be saved shortly.\nID: {item['id'][:8]}…"


def cmd_task(text: str) -> str:
    if not text.strip():
        return "❌ Usage: /task <text>"
    from second_brain.queue import enqueue
    item = enqueue("task", {"title": text[:80], "body": text, "type": "Task", "tags": ["task"]})
    return f"✅ Task queued!\n📋 {text[:80]}"


def cmd_place(text: str) -> str:
    if not text.strip():
        return "❌ Usage: /place <name>, <city>"
    parts = [p.strip() for p in text.split(",", 2)]
    name = parts[0] if parts else text
    city = parts[1] if len(parts) > 1 else ""
    notes = parts[2] if len(parts) > 2 else ""
    from second_brain.queue import enqueue
    item = enqueue("place", {"name": name, "city": city, "notes": notes, "category": "Restaurant"})
    return f"✅ Place queued!\n📍 {name}, {city}"


def cmd_status() -> str:
    from second_brain.queue import stats as queue_stats
    from second_brain.vectorstore import vectorstore
    from second_brain.config import settings

    q = queue_stats()

    counts = {}
    for col in settings.all_collections:
        try:
            c = vectorstore.get(col)
            counts[col] = c.count() if c else 0
        except Exception:
            counts[col] = "?"

    col_lines = "\n".join(f"  • {k}: {v} chunks" for k, v in counts.items())
    return (
        f"📊 Second Brain Status\n\n"
        f"🗂 Collections:\n{col_lines}\n\n"
        f"📬 Queue: {q['pending']} pending · {q['done']} done · {q['failed']} failed"
    )


COMMANDS = {
    "/wiki-ingest": cmd_wiki_ingest,
    "/ingest":      cmd_ingest,
    "/ask":         cmd_ask,
    "/note":        cmd_note,
    "/task":        cmd_task,
    "/place":       cmd_place,
}


def run(raw_input: str) -> str:
    raw_input = raw_input.strip()
    for cmd, handler in COMMANDS.items():
        if raw_input.lower().startswith(cmd):
            args = raw_input[len(cmd):].strip()
            if cmd == "/status":
                return cmd_status()
            return handler(args)

    if raw_input.lower() == "/status":
        return cmd_status()

    return (
        "🤖 Unknown command. Available:\n"
        "  /wiki-ingest <url>    — ingest + synthesize wiki note\n"
        "  /ingest <url>         — ingest URL to ChromaDB only\n"
        "  /ask <question>       — query the brain\n"
        "  /note <text>          — save a note\n"
        "  /task <text>          — save a task\n"
        "  /place <name>, <city> — save a place\n"
        "  /status               — collection + queue stats"
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/command.py '<command>'")
        sys.exit(1)
    print(run(" ".join(sys.argv[1:])))

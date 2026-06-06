#!/usr/bin/env python3
"""
PersGraph Debrief Generator
Pulls recent activity from ChromaDB + SQLite, synthesizes with Ollama, writes data/debrief.json

Usage:
    PYTHONPATH=. .venv/bin/python scripts/debrief.py [today|week|month]
"""

import sys
import os
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))


def get_date_range(period: str):
    today = datetime.now(timezone.utc).date()
    if period == "today":
        start = today
    elif period == "month":
        start = today - timedelta(days=30)
    else:  # week default
        start = today - timedelta(days=7)
    return start, today


def get_chroma_data(start_date, end_date):
    """Fetch recent notes + URLs from ChromaDB."""
    notes, urls = [], []
    try:
        from second_brain.vectorstore import vectorstore

        for col_name in ("notes",):
            try:
                col = vectorstore.get(col_name)
                if col is None:
                    continue
                result = col.get(include=["documents", "metadatas"])
                for doc, meta in zip(result.get("documents", []), result.get("metadatas", [])):
                    raw_date = meta.get("ingested_at", "")[:10]
                    try:
                        d = datetime.strptime(raw_date, "%Y-%m-%d").date()
                    except ValueError:
                        continue
                    if start_date <= d <= end_date:
                        notes.append({"text": doc[:300], "date": raw_date, "source": meta.get("source", "")})
            except Exception as e:
                print(f"  ChromaDB {col_name}: {e}", file=sys.stderr)

        for col_name in ("urls",):
            try:
                col = vectorstore.get(col_name)
                if col is None:
                    continue
                result = col.get(include=["documents", "metadatas"])
                seen = set()
                for doc, meta in zip(result.get("documents", []), result.get("metadatas", [])):
                    raw_date = meta.get("ingested_at", "")[:10]
                    try:
                        d = datetime.strptime(raw_date, "%Y-%m-%d").date()
                    except ValueError:
                        continue
                    if start_date <= d <= end_date:
                        url = meta.get("source", meta.get("url", ""))
                        if url in seen:
                            continue
                        seen.add(url)
                        domain = urlparse(url).netloc or "unknown"
                        title = meta.get("title", doc[:80])
                        urls.append({"title": title, "domain": domain, "url": url, "date": raw_date})
            except Exception as e:
                print(f"  ChromaDB {col_name}: {e}", file=sys.stderr)

    except Exception as e:
        print(f"Warning: ChromaDB unavailable — {e}", file=sys.stderr)

    return notes, urls


def get_sqlite_data(start_date, end_date):
    """Fetch tasks + notes from SQLite."""
    notes, tasks = [], []
    try:
        from second_brain.notes import list_all

        for note_type, target in (("note", notes), ("task", tasks)):
            try:
                items = list_all(item_type=note_type)
                for item in items:
                    raw = getattr(item, "updated_at", None) or getattr(item, "created_at", None) or ""
                    try:
                        d = datetime.fromisoformat(str(raw)[:10]).date()
                    except Exception:
                        continue
                    if start_date <= d <= end_date:
                        text = getattr(item, "content", None) or getattr(item, "text", None) or str(item)
                        target.append({"type": note_type, "text": str(text)[:200], "date": str(raw)[:10]})
            except Exception as e:
                print(f"  SQLite {note_type}: {e}", file=sys.stderr)
    except Exception as e:
        print(f"Warning: SQLite unavailable — {e}", file=sys.stderr)

    return notes, tasks


def synthesize_topics(chroma_notes, urls, sqlite_notes, tasks):
    """Cluster activity into topics using local Ollama LLM."""
    all_items = []
    for n in chroma_notes:
        all_items.append(f"Note: {n.get('text', '')}")
    for u in urls:
        all_items.append(f"URL ingested: {u.get('title', '')} [{u.get('domain', '')}]")
    for n in sqlite_notes:
        all_items.append(f"Note: {n.get('text', '')}")
    for t in tasks:
        all_items.append(f"Task: {t.get('text', '')}")

    if not all_items:
        return []

    content = "\n".join(all_items[:40])

    prompt = f"""You are an analyst. Cluster these recent activity items into 3-6 meaningful topic groups.
Return ONLY valid JSON — no markdown, no explanation.

Items:
{content}

JSON format:
{{"topics": [{{"name": "Topic Name", "highlights": ["point 1", "point 2", "point 3"]}}]}}"""

    try:
        from second_brain.config import settings
        from ollama import Client
        import httpx

        client = Client(
            host=settings.ollama_base_url,
            timeout=httpx.Timeout(timeout=300.0, connect=10.0)
        )
        # Stream to avoid timeout on large models over Tailscale
        text = ""
        for chunk in client.generate(model=settings.llm_model, prompt=prompt, stream=True):
            text += chunk.get("response", "") if isinstance(chunk, dict) else str(chunk)

        # Strip markdown fences if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        data = json.loads(text.strip())
        topics = []
        for t in data.get("topics", []):
            t["source_count"] = len(t.get("highlights", []))
            topics.append(t)
        return topics

    except Exception as e:
        print(f"Warning: Topic synthesis failed — {e}", file=sys.stderr)
        # Fallback: return a generic topic with raw items
        if all_items:
            return [{"name": "Recent Activity", "highlights": all_items[:5], "source_count": len(all_items)}]
        return []


def main():
    period = sys.argv[1] if len(sys.argv) > 1 else "week"
    if period not in ("today", "week", "month"):
        print(f"❌ Invalid period '{period}'. Use: today / week / month")
        sys.exit(1)

    start_date, end_date = get_date_range(period)
    print(f"📊 Generating debrief: {period} ({start_date} → {end_date})")

    chroma_notes, chroma_urls = get_chroma_data(start_date, end_date)
    sqlite_notes, sqlite_tasks = get_sqlite_data(start_date, end_date)

    print(f"   ChromaDB notes: {len(chroma_notes)} | urls: {len(chroma_urls)}")
    print(f"   SQLite notes: {len(sqlite_notes)} | tasks: {len(sqlite_tasks)}")

    topics = synthesize_topics(chroma_notes, chroma_urls, sqlite_notes, sqlite_tasks)
    print(f"   Topics synthesized: {len(topics)}")

    all_notes_items = sqlite_notes + sqlite_tasks
    all_notes_items.sort(key=lambda x: x.get("date", ""), reverse=True)

    output = {
        "period": period,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "notes_saved": len(chroma_notes) + len(sqlite_notes),
            "urls_ingested": len(chroma_urls),
            "tasks_completed": len(sqlite_tasks),
            "commands_run": 0
        },
        "topics": topics,
        "ingested": chroma_urls[:10],
        "notes": all_notes_items[:10],
        "langfuse": {
            "commands_run": 0,
            "avg_latency_ms": 0,
            "total_cost_usd": 0.0
        }
    }

    out_file = BASE_DIR / "data" / "debrief.json"
    out_file.parent.mkdir(exist_ok=True)
    out_file.write_text(json.dumps(output, indent=2, default=str))

    print(f"\n✅ Saved → {out_file}")
    print(f"   Stats: {output['stats']}")
    if topics:
        print(f"   Topics: {', '.join(t['name'] for t in topics)}")


if __name__ == "__main__":
    main()

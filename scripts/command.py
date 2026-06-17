#!/usr/bin/env python3
"""
Second Brain — Slash Command Handler

Handles commands sent from Telegram via OpenClaw:
  /ingest <url>              — ingest a URL into the brain
  /ask <question>            — query the brain
  /note <text>               — save a quick note
  /task <text>               — save a task
  /place <name>, <city>      — save a place
  /bucketlist ...            — save/list bucket list places
  /digest [today|week]       — on-demand summary report
  /status                    — show queue + collection stats

Usage:
    python scripts/command.py "/ingest https://example.com"
    python scripts/command.py "/ask what is RAG?"
    python scripts/command.py "/note buy groceries"
    python scripts/command.py "/bucketlist add Kurama Onsen, Kyoto, scenic day trip"
    python scripts/command.py "/digest today"
    python scripts/command.py "/status"
"""

import sys
import os
import json
import time
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()
load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")

LOCAL_TZ = ZoneInfo("America/Los_Angeles")


def _now_local() -> datetime:
    return datetime.now(LOCAL_TZ)


def _parse_datetime_loose(text: str) -> tuple[datetime | None, str | None]:
    s = text.strip()
    now = _now_local()

    m = re.match(r'^in\s+(\d+)\s*([mh])\s+(.+)$', s, re.I)
    if m:
        qty = int(m.group(1))
        unit = m.group(2).lower()
        title = m.group(3).strip()
        dt = now + (timedelta(hours=qty) if unit == 'h' else timedelta(minutes=qty))
        return dt, title

    m = re.match(r'^(tomorrow)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s+(.+)$', s, re.I)
    if m:
        day_word, hour_s, minute_s, ampm, title = m.groups()
        hour = int(hour_s)
        minute = int(minute_s or 0)
        if ampm:
            ampm = ampm.lower()
            if ampm == 'pm' and hour != 12:
                hour += 12
            if ampm == 'am' and hour == 12:
                hour = 0
        base = now + timedelta(days=1)
        dt = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return dt, title.strip()

    m = re.match(r'^(.+?)\s*,\s*(\d{4}-\d{2}-\d{2})(?:\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?$', s, re.I)
    if m:
        title, date_s, hour_s, minute_s, ampm = m.groups()
        try:
            dt = datetime.fromisoformat(date_s).replace(tzinfo=LOCAL_TZ)
            if hour_s:
                hour = int(hour_s)
                minute = int(minute_s or 0)
                if ampm:
                    ampm = ampm.lower()
                    if ampm == 'pm' and hour != 12:
                        hour += 12
                    if ampm == 'am' and hour == 12:
                        hour = 0
                dt = dt.replace(hour=hour, minute=minute)
            return dt, title.strip()
        except ValueError:
            return None, None

    m = re.match(r'^(.+?)\s*,\s*(\w+\s+\d{1,2})(?:\s*,?\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?$', s, re.I)
    if m:
        title, month_day, hour_s, minute_s, ampm = m.groups()
        try:
            dt = datetime.strptime(f"{month_day} {now.year}", "%b %d %Y")
        except ValueError:
            try:
                dt = datetime.strptime(f"{month_day} {now.year}", "%B %d %Y")
            except ValueError:
                return None, None
        dt = dt.replace(tzinfo=LOCAL_TZ)
        if hour_s:
            hour = int(hour_s)
            minute = int(minute_s or 0)
            if ampm:
                ampm = ampm.lower()
                if ampm == 'pm' and hour != 12:
                    hour += 12
                if ampm == 'am' and hour == 12:
                    hour = 0
            dt = dt.replace(hour=hour, minute=minute)
        return dt, title.strip()

    return None, None


def _fmt_local(dt: datetime) -> str:
    return dt.astimezone(LOCAL_TZ).strftime("%b %d, %-I:%M %p %Z")


def _extract_due_from_body(text: str) -> str | None:
    m = re.search(r'(?:date|due):(\d{4}-\d{2}-\d{2})', text)
    return m.group(1) if m else None


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# User registry
# ---------------------------------------------------------------------------

def _load_users() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "users.json")
    try:
        with open(config_path) as f:
            return json.load(f)
    except Exception:
        return {}


USERS = _load_users()


def resolve_user(sender_id: str | None) -> dict:
    """Resolve a Telegram sender_id to a user record. Falls back to guest."""
    if sender_id and str(sender_id) in USERS:
        return USERS[str(sender_id)]
    return {"name": "guest", "tier": "guest", "model": "haiku", "display": "Guest"}


def _parse_user_flag(args: str) -> tuple[str, str | None]:
    """Extract --user <name> from args. Returns (cleaned_args, user_name_or_None)."""
    import re
    match = re.search(r'--user\s+(\S+)', args)
    if match:
        user_name = match.group(1)
        cleaned = args[:match.start()].strip() + ' ' + args[match.end():].strip()
        return cleaned.strip(), user_name
    return args, None


def cmd_pghelp(args: str = "") -> str:
    return (
        "🧭 PersGraph command guide (full command list)\n"
        "\n"
        "QUICK CAPTURE\n"
        "• /note <text> — save a quick note\n"
        "• /task <text> — save a task or to-do\n"
        "• /place <name>, <city> [, notes] — save a place\n"
        "• /places [query] — list or search saved places\n"
        "\n"
        "KNOWLEDGE\n"
        "• /wiki-ingest <url> — create a curated Obsidian wiki note, then index it\n"
        "• /ingest <url> [--user <name>] — raw URL ingest into semantic search\n"
        "• /ask <question> [--user <name>] — ask PersGraph what it knows\n"
        "\n"
        "PLANNING\n"
        "• /appointment <title>, <date/time> — save an appointment\n"
        "• /appointment list — list appointments\n"
        "• /schedule [week] — show upcoming schedule\n"
        "\n"
        "REPORTS & UTILITIES\n"
        "• /digest [today|week] — generate a summary\n"
        "• /debrief [today|week|month] — generate an activity debrief\n"
        "• /bucketlist ... — save/list bucket list places\n"
        "• /TripToggle On|Off [opts] — enable/disable Explore Mode\n"
        "• /sport [soccer|football|nba] — sports schedule\n"
        "• /status — collection + queue stats\n"
        "• /status service — app service + route health\n"
        "• /status ops — smoke test + deploy posture\n"
        "\n"
        "EXAMPLES\n"
        "• /note Call dentist tomorrow\n"
        "• /place Blue Bottle Coffee, San Francisco, good espresso\n"
        "• /appointment Dentist, Jun 20, 2pm\n"
        "• /schedule week\n"
        "• /bucketlist add Kurama Onsen, Kyoto, scenic day trip\n"
        "• /ask what do I know about Japan trip plans\n"
        "• /ingest https://example.com/article\n"
        "\n"
        "Tip: use /pghelp anytime for this guide."
    )


def cmd_ingest(args: str, user: dict | None = None) -> str:
    # Parse --user flag
    args, flag_user = _parse_user_flag(args)

    url = args.strip()
    if not url:
        return "❌ Usage: /ingest <url> [--user <name>]"
    
    # Prepare optional learning metadata
    ingest_event_id = None

    # Auto-apply Freedium for Medium URLs
    original_url = url
    if "medium.com" in url and "freedium" not in url:
        url = f"https://freedium-mirror.cfd/{url}"

    # Auto-detect tags
    tags = []
    if "medium.com" in args or "freedium" in url:
        tags.append("medium")
    if "youtube.com" in args or "youtu.be" in args:
        tags.append("youtube")
    if "github.com" in args:
        tags.append("github")

    user_name = flag_user or (user["name"] if user and user["name"] != "guest" else None)
    if user_name:
        tags.append(f"user:{user_name}")

    from second_brain.connectivity import chromadb_reachable
    from second_brain.queue import enqueue_retry, DEP_CHROMADB, DEP_OLLAMA

    if not chromadb_reachable():
        enqueue_retry("url", {"url": url, "tags": tags}, needs=[DEP_CHROMADB])
        return "⏳ Queued for retry\n📶 Knowledge backend is offline — will ingest when it's back\n🔗 {}".format(original_url)

    from second_brain.ingesters.url import URLIngester
    try:
        result = URLIngester().ingest(url, tags=tags)
    except Exception as e:
        err = str(e)
        err_l = err.lower()
        backend_unavailable = any(k in err_l for k in ["connection refused", "failed to connect", "timed out", "timeout", "name or service not known", "temporary failure in name resolution", "404"])
        context_overflow = "context length" in err_l
        if backend_unavailable:
            enqueue_retry("url", {"url": url, "tags": tags}, needs=[DEP_OLLAMA, DEP_CHROMADB])
            return "⏳ Saved for retry\n🧠 Embedding backend not ready right now — will ingest automatically later\n🔗 {}".format(original_url)
        if context_overflow:
            return f"❌ Ingestion failed: article text still exceeds embedding context after fallback chunking: {err}"
        return f"❌ Ingestion failed: {err}"

    if result.success:
        # Record ingest as learning event for feedback loop
        try:
            from second_brain import learning_db
            ingest_event_id = learning_db.record_event(
                event_type="command_usage",
                metadata={"command": "/ingest", "url": url, "collection": result.collection, "chunks": result.chunks_new}
            )
        except Exception:
            pass  # Learning layer not critical
        return (
            "✅ Ingested!\n"
            f"📦 Collection: {result.collection}\n"
            f"✂️ Chunks: {result.chunks_new} new / {result.chunks_total} total\n"
            f"🏷️ Tags: {', '.join(result.tags) or 'none'}"
        )

    errors = '; '.join(result.errors)
    errors_l = errors.lower()
    if any(k in errors_l for k in ["connection refused", "failed to connect", "timed out", "timeout", "name or service not known", "temporary failure in name resolution", "404"]):
        enqueue_retry("url", {"url": url, "tags": tags}, needs=[DEP_OLLAMA, DEP_CHROMADB])
        return "⏳ Saved for retry\n🧠 Embedding backend not ready right now — will ingest automatically later\n🔗 {}".format(original_url)

    return f"❌ Ingestion failed: {errors}"

def cmd_ask(question: str, user: dict | None = None) -> str:
    """Retrieve relevant chunks from the brain. Claude synthesizes the answer."""
    question, flag_user = _parse_user_flag(question)

    if not question.strip():
        return "❌ Usage: /ask <question> [--user <name>]"
    
    # Prepare optional learning metadata
    ask_event_id = None

    from second_brain.connectivity import chromadb_reachable
    if not chromadb_reachable():
        return (
            "📶 Can't reach the knowledge base right now — Windows machine is offline.\n"
            "Try again when it's back, or save this as a note: /note \"<your question>\""
        )

    from second_brain.embeddings import embedder
    from second_brain.vectorstore import vectorstore

    try:
        q_vec = embedder.embed(question)
    except Exception as e:
        err = str(e)
        if any(k in err.lower() for k in ["model", "ollama", "embed", "embedding", "404"]):
            return (
                "🧠 The knowledge base is reachable, but embeddings are temporarily unavailable.\n"
                "Immediate semantic lookup is paused until the embedding model comes back.\n"
                "You can still use /note, /task, /place, /appointment, and /schedule right now."
            )
        return f"❌ Ask failed: {err}"

    where = {"$contains": f"user:{flag_user}"} if flag_user else None
    results = vectorstore.query_all(q_vec, top_k=5, where=where)
    if not results:
        scope_msg = f" tagged --user {flag_user}" if flag_user else ""
        return f"🤷 Nothing relevant found{scope_msg}. Try /ingest some articles first!"

    scope_label = f" [scoped to: {flag_user}]" if flag_user else ""
    output_lines = [f"📖 Retrieved {len(results)} chunks for: \"{question}\"{scope_label}\n"]
    for i, r in enumerate(results, 1):
        meta = r.get("metadata", {})
        title = meta.get("title", "Unknown source")
        source_type = meta.get("source_type", "web")
        score = r.get("score", 0)
        output_lines.append(f"[{i}] {title} ({source_type}, score={score})")
        output_lines.append(r['text'].strip())
        output_lines.append("")

    # Record ask as learning event for feedback loop
    try:
        from second_brain import learning_db
        ask_event_id = learning_db.record_event(
            event_type="command_usage",
            metadata={"command": "/ask", "question": question[:100], "result_count": len(results)}
        )
    except Exception:
        pass  # Learning layer not critical

    return "\n".join(output_lines)

def cmd_wiki_ingest(text: str) -> str:
    raw = text.strip()
    if not raw:
        return "❌ Usage: /wiki-ingest <url>"

    if not re.match(r"^https?://", raw, re.I):
        return "❌ /wiki-ingest currently expects a URL"

    from second_brain.ingesters.url import URLIngester
    from second_brain.queue import enqueue_retry, DEP_CHROMADB, DEP_OLLAMA
    from second_brain.connectivity import chromadb_reachable

    def _slugify(text: str, max_len: int = 80) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        return (slug[:max_len].strip("-") or "note")

    def _wiki_dir() -> Path:
        try:
            from second_brain.app_config import app_config
            vault_path = str(app_config._get("obsidian", "vault_path", default="~/AgenticHub/InsightsData"))
        except Exception:
            from second_brain.config import settings
            vault_path = settings.obsidian_vault_path
        return Path(os.path.expanduser(vault_path)) / "wiki" / "articles"

    url = raw
    if "medium.com" in url and "freedium" not in url:
        url = f"https://freedium-mirror.cfd/{url}"

    try:
        text_content, title = URLIngester()._fetch(url)
    except Exception as e:
        return f"❌ Could not fetch source: {e}"

    if not text_content.strip():
        return "❌ Could not extract readable content from that URL"

    title = (title or "Untitled").strip()
    date_str = _now_local().strftime("%Y-%m-%d")
    wiki_dir = _wiki_dir()
    wiki_dir.mkdir(parents=True, exist_ok=True)
    out_path = wiki_dir / f"{date_str}-{_slugify(title)}.md"

    clean_words = text_content.split()
    fallback_overview = " ".join(clean_words[:140]).strip() or "Source captured for later curation."
    fallback_key_points = [
        " ".join(clean_words[i:i + 45]).strip()
        for i in range(140, min(len(clean_words), 365), 45)
        if " ".join(clean_words[i:i + 45]).strip()
    ][:5]
    fallback_references = [
        " ".join(clean_words[i:i + 35]).strip()
        for i in range(365, min(len(clean_words), 540), 35)
        if " ".join(clean_words[i:i + 35]).strip()
    ][:3]

    overview = fallback_overview
    key_points = fallback_key_points
    why_it_matters = "Add why this note matters to your work, decisions, or memory graph."
    references = fallback_references
    synthesis_note = ""

    try:
        from second_brain.llm import complete
        synthesis_source = text_content[:12000]
        prompt = f"""You are writing a concise personal wiki note from a source article.

Return plain JSON with this exact schema:
{{
  \"overview\": \"2-4 sentence summary\",
  \"key_points\": [\"bullet 1\", \"bullet 2\", \"bullet 3\"],
  \"why_it_matters\": \"1-2 sentence practical relevance\",
  \"reference_excerpts\": [\"short quote or excerpt 1\", \"short quote or excerpt 2\"]
}}

Rules:
- Be concrete, not fluffy.
- Keep key_points to 3-5 items.
- Keep excerpts short.
- No markdown fences.
- Output valid JSON only.

Title: {title}
URL: {url}
Date: {date_str}

Source text:
{synthesis_source}
"""
        raw_json = complete(prompt, tier="fast", max_tokens=900).strip()
        data = json.loads(raw_json)
        overview = (str(data.get("overview") or overview)).strip()
        key_points = [str(x).strip() for x in (data.get("key_points") or []) if str(x).strip()][:5] or key_points
        why_it_matters = (str(data.get("why_it_matters") or why_it_matters)).strip()
        references = [str(x).strip() for x in (data.get("reference_excerpts") or []) if str(x).strip()][:3] or references
        synthesis_note = "\n✨ LLM-curated summary generated"
    except Exception:
        synthesis_note = "\n📝 Used extraction fallback; LLM summary unavailable"

    safe_title = title.replace('"', "'")
    markdown = (
        "---\n"
        f"title: \"{safe_title}\"\n"
        f"source: \"{url}\"\n"
        f"date: {date_str}\n"
        "tags: [wiki, curated, web]\n"
        "---\n\n"
        f"# {title}\n\n"
        "## Overview\n"
        f"{overview}\n\n"
        "## Key Points\n"
        + ("\n".join(f"- {point}" for point in key_points) if key_points else "- Add key takeaways after review.")
        + "\n\n## Why It Matters\n"
        + f"{why_it_matters}\n\n"
        + "## Source\n"
        + f"- URL: {url}\n"
        + f"- Captured: {date_str}\n\n"
        + "## Reference Excerpts\n"
        + (("\n".join(f"> {ref}" for ref in references)) if references else "> No reference excerpts captured.")
        + "\n"
    )
    out_path.write_text(markdown, encoding="utf-8")

    vault_root = str(wiki_dir.parent.parent)
    tags = ["wiki", "curated", "obsidian"]
    index_note = ""

    if not chromadb_reachable():
        enqueue_retry("obsidian", {"vault": vault_root, "tags": tags}, needs=[DEP_CHROMADB])
        index_note = "\n📶 Vault note saved; semantic indexing queued until backend returns"
    else:
        try:
            from second_brain.ingesters.obsidian import ObsidianIngester
            result = ObsidianIngester(vault_path=vault_root).ingest_file(str(out_path), tags=tags)
            if result.success:
                index_note = f"\n🧠 Indexed in {result.collection}: {result.chunks_new} new chunks"
            else:
                errors = "; ".join(result.errors)
                if any(k in errors.lower() for k in ["model", "ollama", "embed", "embedding", "404"]):
                    enqueue_retry("obsidian", {"vault": vault_root, "tags": tags}, needs=[DEP_OLLAMA, DEP_CHROMADB])
                    index_note = "\n🧠 Vault note saved; indexing queued until embeddings/backend return"
                else:
                    index_note = f"\n⚠️ Vault note saved, but indexing failed: {errors}"
        except Exception as e:
            err = str(e)
            if any(k in err.lower() for k in ["model", "ollama", "embed", "embedding", "404"]):
                enqueue_retry("obsidian", {"vault": vault_root, "tags": tags}, needs=[DEP_OLLAMA, DEP_CHROMADB])
                index_note = "\n🧠 Vault note saved; indexing queued until embeddings/backend return"
            else:
                index_note = f"\n⚠️ Vault note saved, but indexing failed: {err}"

    return (
        f"✅ Wiki note saved!\n"
        f"📝 {title}\n"
        f"📂 {out_path}\n"
        f"🔗 {url}"
        f"{synthesis_note}"
        f"{index_note}"
    )


def cmd_note(text: str) -> str:
    if not text.strip():
        return "❌ Usage: /note <text>"
    from second_brain.queue import enqueue
    item = enqueue("note", {"title": text[:80], "body": text, "type": "Note", "tags": ["note", "quick-capture"]})
    # Record command usage as learning event (optional feedback)
    try:
        from second_brain import learning_db
        learning_db.record_event(
            event_type="command_usage",
            metadata={"command": "/note", "item_id": item['id'], "title": text[:80]}
        )
    except Exception:
        pass  # Learning layer not critical for note capture
    return f"✅ Note queued! Will be saved shortly.\nID: {item['id'][:8]}…"


def cmd_task(text: str) -> str:
    if not text.strip():
        return "❌ Usage: /task <text>"
    from second_brain.queue import enqueue
    item = enqueue("task", {"title": text[:80], "body": text, "type": "Task", "tags": ["task"]})
    return f"✅ Task queued!\n📋 {text[:80]}"


def cmd_place(text: str) -> str:
    if not text.strip():
        return "❌ Usage: /place <name>, <city> [, notes]"
    parts = [p.strip() for p in text.split(",", 2)]
    name = parts[0] if parts else text
    city = parts[1] if len(parts) > 1 else ""
    notes = parts[2] if len(parts) > 2 else ""
    from second_brain.places_db import save  # SQLite — instant, no VPN needed
    result = save(name=name, city=city, notes=notes, category="Restaurant")
    tags = result.get("tags_list", [])
    tag_str = f" · #{' #'.join(tags)}" if tags else ""
    maps = result.get("maps_url", "")
    maps_str = f"\n🗺 {maps}" if maps else ""
    return f"✅ Saved!\n📍 {name}, {city}{tag_str}{maps_str}"


def cmd_places(text: str) -> str:
    """List saved places, optionally filtered by city."""
    from second_brain.places_db import list_all, search, count as places_count, _expand_city
    raw_filter = text.strip() or None
    city_filter = _expand_city(raw_filter) if raw_filter else None

    if city_filter:
        results = search(city_filter, city=city_filter, top_k=20)
        if not results:
            results = list_all(city=city_filter, limit=20)
        header = f"📍 Places in {city_filter} ({len(results)} found)"
    else:
        results = list_all(limit=30)
        total = places_count()
        header = f"📍 All places ({total} total, showing {len(results)})"

    if not results:
        return f"No places found{' in ' + city_filter if city_filter else ''}. Save one with /place <name>, <city>"

    lines = [header, ""]
    for p in results:
        name = p.get("name", "?")
        city = p.get("city", "")
        cat = p.get("category", "")
        notes = p.get("notes", "")
        rating = p.get("rating")
        stars = f" {'⭐' * int(rating)}" if rating else ""
        # Keep a short, readable description on the primary line.
        desc = notes.strip() if notes else ""
        if desc:
            desc = desc[:80]
        desc_str = f" — {desc}" if desc else ""
        maps = p.get("maps_url", "")
        maps_str = f"\n  🗺 {maps}" if maps else ""
        lines.append(f"• {name}, {city} [{cat}]{stars}{desc_str}{maps_str}")

    return "\n".join(lines)


def _llm_format(prompt: str, fallback: str, tier: str = "fast") -> str:
    try:
        from second_brain.llm import complete
        out = complete(prompt, tier=tier, max_tokens=900).strip()
        return out or fallback
    except Exception:
        return fallback


def cmd_bucketlist(text: str) -> str:
    from second_brain.places_db import save, list_all, search, _expand_city

    raw = text.strip()
    if not raw:
        return "❌ Usage: /bucketlist add <name>, <city> [, intent] | /bucketlist list [city]"

    lower = raw.lower()
    if lower.startswith("add "):
        payload = raw[4:].strip()
        parts = [p.strip() for p in payload.split(",", 2)]
        name = parts[0] if parts else payload
        city = parts[1] if len(parts) > 1 else ""
        notes = parts[2] if len(parts) > 2 else ""
        result = save(
            name=name,
            city=city,
            notes=notes,
            category="BucketList",
            extra_tags=["bucketlist", "want-to-go"],
        )
        base = (
            f"Saved bucket list item.\n"
            f"Name: {result.get('name','')}\n"
            f"Location: {result.get('city','') or 'Unknown'}\n"
            f"Intent: {result.get('notes','') or 'none'}\n"
            f"Maps: {result.get('maps_url','')}"
        )
        prompt = f"""Turn this into a visually formatted Telegram confirmation.
Use short sections, bullets, and emoji. Keep it compact.

{base}
"""
        return _llm_format(prompt, f"✅ Bucket list saved!\n• {name} — {city or 'Unknown'}\n↳ {notes or 'Added for later'}", tier="fast")

    query = raw
    if lower.startswith("list"):
        query = raw[4:].strip()

    city_filter = _expand_city(query) if query else None
    if query:
        results = [r for r in search(query, city=city_filter, top_k=40) if r.get('category') == 'BucketList']
        if city_filter and not results:
            results = list_all(city=city_filter, category='BucketList', limit=25)
    else:
        results = list_all(category='BucketList', limit=25)

    if not results:
        return "🧭 No bucket list items found yet. Add one with /bucketlist add <name>, <city>, <intent>"

    rows = []
    for r in results:
        rows.append(f"- {r.get('name','?')} | city={r.get('city','')} | notes={r.get('notes','')} | maps={r.get('maps_url','')}")
    base = "Bucket list items:\n" + "\n".join(rows)
    prompt = f"""Format this as a visually pleasing Telegram bucket list view.
Rules:
- Use bullets
- First line for each item: • Name — Location
- Optional second indented line: ↳ intent/details
- Keep it compact
- Add a short title line

{base}
"""
    fallback_lines = ["🧭 Bucket List", ""]
    for r in results:
        fallback_lines.append(f"• {r.get('name','?')} — {r.get('city','Unknown')}")
        if r.get('notes'):
            fallback_lines.append(f"  ↳ {r.get('notes')}")
    return _llm_format(prompt, "\n".join(fallback_lines), tier="fast")


def cmd_digest(text: str) -> str:
    from second_brain.notes_db import list_all as list_notes
    from second_brain.places_db import list_all as list_places

    mode = (text or "today").strip().lower()
    now = _now_local()
    horizon_days = 1 if mode in ("", "today", "now") else 7

    tasks = list_notes(item_type="Task", limit=20)
    appointments = list_notes(item_type="Appointment", limit=20)
    notes = list_notes(item_type="Note", limit=12)
    places = list_places(limit=20)
    bucket = [p for p in places if p.get('category') == 'BucketList'][:8]

    upcoming = []
    for item in appointments:
        ds = (item.get('date') or '').strip()
        if not ds:
            continue
        try:
            dt = datetime.fromisoformat(ds)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=LOCAL_TZ)
            if now <= dt <= now + timedelta(days=horizon_days):
                upcoming.append((dt, item.get('title','Untitled')))
        except Exception:
            continue
    upcoming.sort(key=lambda x: x[0])

    task_lines = [f"- {t.get('title','')[:90]}" for t in tasks[:8]]
    appt_lines = [f"- {title} @ {_fmt_local(dt)}" for dt, title in upcoming[:8]]
    note_lines = [f"- {n.get('title','')[:90]}" for n in notes[:5]]
    bucket_lines = [f"- {b.get('name','?')} ({b.get('city','')})" for b in bucket[:5]]

    base = f"""Mode: {mode or 'today'}
Now: {_fmt_local(now)}

Tasks:
{chr(10).join(task_lines) if task_lines else '- none'}

Appointments:
{chr(10).join(appt_lines) if appt_lines else '- none'}

Recent notes:
{chr(10).join(note_lines) if note_lines else '- none'}

Bucket list:
{chr(10).join(bucket_lines) if bucket_lines else '- none'}
"""
    prompt = f"""Create a visually formatted on-demand digest for Telegram.
Rules:
- Use a crisp title
- Use sections with emoji
- Prioritize what matters now
- Highlight upcoming appointments and top tasks
- End with a short 'Next moves' section
- Keep it concise but polished

{base}
"""
    fallback = (
        f"📋 Digest — {mode or 'today'}\n\n"
        f"Appointments\n" + ("\n".join(f"• {title} — {_fmt_local(dt)}" for dt, title in upcoming[:5]) if upcoming else "• None") +
        f"\n\nTasks\n" + ("\n".join(f"• {t.get('title','')[:90]}" for t in tasks[:5]) if tasks else "• None") +
        f"\n\nRecent notes\n" + ("\n".join(f"• {n.get('title','')[:90]}" for n in notes[:3]) if notes else "• None")
    )
    return _llm_format(prompt, fallback, tier="fast")


def cmd_sport(text: str) -> str:
    from second_brain.sports import get_sports_status
    return get_sports_status(text.strip())


def cmd_appointment(text: str) -> str:
    from second_brain.notes import save, list_all

    raw = text.strip()
    if not raw:
        return "❌ Usage: /appointment <title>, <date/time> or /appointment list"
    
    # Prepare optional learning metadata
    appt_event_id = None

    if raw.lower() == 'list':
        rows = list_all(item_type='Appointment', limit=50)
        items = []
        now = _now_local()
        for r in rows:
            ds = (r.get('date') or '').strip()
            if not ds:
                continue
            try:
                dt = datetime.fromisoformat(ds)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=LOCAL_TZ)
                if dt >= now - timedelta(days=1):
                    items.append((dt, r))
            except Exception:
                continue
        items.sort(key=lambda x: x[0])
        if not items:
            return "📅 No upcoming appointments."
        lines = ["📅 Upcoming appointments", ""]
        for dt, r in items[:10]:
            lines.append(f"• {r.get('title','Untitled')} — {_fmt_local(dt)}")
        return "\n".join(lines)

    dt, title = _parse_datetime_loose(raw)
    if not dt or not title:
        return "❌ Usage: /appointment <title>, <date/time> (e.g. /appointment Dentist, Jun 20, 2pm)"

    item = save(title=title, item_type='Appointment', date=dt.isoformat(), tags=['appointment'])
    # Record appointment as learning event for feedback loop
    try:
        from second_brain import learning_db
        appt_event_id = learning_db.record_event(
            event_type="command_usage",
            metadata={"command": "/appointment", "title": title, "date": dt.isoformat(), "item_id": item.get('id')}
        )
    except Exception:
        pass  # Learning layer not critical
    return f"✅ Appointment saved!\n📅 {title} — {_fmt_local(dt)}"


def cmd_schedule(text: str) -> str:
    from second_brain.notes import list_all

    mode = (text.strip().lower() or 'today')
    now = _now_local()
    end = now + timedelta(days=7 if mode == 'week' else 1)

    items = []

    for r in list_all(item_type='Appointment', limit=100):
        ds = (r.get('date') or '').strip()
        if not ds:
            continue
        try:
            dt = datetime.fromisoformat(ds)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=LOCAL_TZ)
            if now <= dt <= end:
                items.append((dt, 'Appointment', r.get('title','Untitled')))
        except Exception:
            pass

    for r in list_all(item_type='Task', limit=100):
        due = _extract_due_from_body((r.get('body') or '') + ' ' + (r.get('title') or ''))
        if not due:
            continue
        try:
            dt = datetime.fromisoformat(due).replace(tzinfo=LOCAL_TZ)
            if now <= dt <= end:
                items.append((dt, 'Task', r.get('title','Untitled')))
        except Exception:
            pass

    # Add known trips
    trips = [
        (datetime(2026, 6, 22, tzinfo=LOCAL_TZ), datetime(2026, 7, 1, tzinfo=LOCAL_TZ), "✈️ Japan trip"),
        (datetime(2026, 7, 3, tzinfo=LOCAL_TZ), datetime(2026, 7, 5, tzinfo=LOCAL_TZ), "✈️ Tahoe trip"),
        (datetime(2026, 7, 11, tzinfo=LOCAL_TZ), datetime(2026, 7, 13, tzinfo=LOCAL_TZ), "✈️ Riverside trip"),
    ]
    for start_dt, end_dt, trip_name in trips:
        if now <= start_dt <= end:
            items.append((start_dt, 'Trip', trip_name))

    items.sort(key=lambda x: x[0])
    label = 'Next 7 days' if mode == 'week' else 'Today'
    if not items:
        return f"📅 Schedule — {label}\n\n• Nothing scheduled"

    lines = [f"📅 Schedule — {label}", ""]
    for dt, kind, title in items[:20]:
        lines.append(f"• {_fmt_local(dt)} — {title}")
    return '\n'.join(lines)


def _parse_triptoggle_args(text: str) -> tuple[str, str | None, int | None, str | None]:
    tokens = [t.strip() for t in text.split() if t.strip()]
    if not tokens:
        return "", None, None, None

    action = tokens[0].lower()
    duration = None
    cadence = None
    intensity = None

    for token in tokens[1:]:
        lower = token.lower()
        if lower in {"2h", "4h", "8h", "eod", "trip"}:
            duration = lower
        elif lower.endswith("m") and lower[:-1].isdigit():
            minutes = int(lower[:-1])
            if minutes in {30, 60, 90}:
                cadence = minutes
        elif lower in {"low", "medium", "high"}:
            intensity = lower

    return action, duration, cadence, intensity


def cmd_triptoggle(text: str) -> str:
    from scripts.explore_mode import disable_explore, enable_explore, format_toggle_off, format_toggle_on, status_text, build_suggestion, format_suggestion_message, check_once

    raw = (text or "").strip()
    if not raw:
        return (
            "❌ Usage: /TripToggle On [duration] [cadence] [intensity] | /TripToggle Off\n"
            "Examples: /TripToggle On 4h 60m medium · /TripToggle Off"
        )

    action, duration, cadence, intensity = _parse_triptoggle_args(raw)
    if action == "on":
        state = enable_explore(duration=duration, cadence=cadence, intensity=intensity)
        # Keep the persisted explore-state file aligned with the live toggle path.
        try:
            from second_brain import explore_state as legacy_explore_state
            legacy_explore_state.enable_explore(
                duration_str=duration or "2h",
                cadence_str=f"{cadence or 60}m",
                intensity=intensity or "medium",
            )
        except Exception:
            pass
        toggle_msg = format_toggle_on(state)
        
        # Immediately emit the first suggestion only if it has real location/map backing
        try:
            suggestion = build_suggestion(state=state)
            primary = suggestion.primary_poi
            if getattr(primary, "maps_url", "") or getattr(primary, "id", ""):
                suggestion_msg = format_suggestion_message(suggestion, state)
                return f"{toggle_msg}\n\n{suggestion_msg}"
        except Exception:
            pass
        return toggle_msg
    if action == "off":
        disable_explore(reason="manual")
        try:
            from second_brain import explore_state as legacy_explore_state
            legacy_explore_state.disable_explore()
        except Exception:
            pass
        return format_toggle_off()
    if action == "status":
        return status_text()
    return "❌ Usage: /TripToggle On [duration] [cadence] [intensity] | /TripToggle Off | /TripToggle Status"


def _run(cmd: list[str], timeout: int = 10) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or '').strip()
        err = (r.stderr or '').strip()
        return r.returncode == 0, out or err
    except Exception as e:
        return False, str(e)


def _http_code(url: str, timeout: int = 10) -> str:
    ok, out = _run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", str(timeout), url], timeout=timeout + 2)
    return out if ok else "ERR"


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _service_status_view() -> str:
    service = "persgraph-web.service"
    lines = ["🛠 PersGraph Status — Service", ""]

    ok, active = _run(["systemctl", "is-active", service])
    active_text = active if active else "unknown"
    lines.append(f"• Service: {active_text}")

    ok_pid, pid = _run(["systemctl", "show", "-p", "MainPID", "--value", service])
    if ok_pid and pid and pid != "0":
        lines.append(f"• PID: {pid}")

    ok_started, started = _run(["systemctl", "show", "-p", "ActiveEnterTimestamp", "--value", service])
    if ok_started and started:
        lines.append(f"• Started: {started}")

    ok_port, port_out = _run(["bash", "-lc", "ss -ltnp | grep ':8766 '"])
    lines.append(f"• Port 8766: {'listening' if ok_port and port_out else 'not listening'}")

    public_root = _http_code("https://persgraph.simplicore.ai/")
    public_login = _http_code("https://persgraph.simplicore.ai/login")
    local_root = _http_code("http://127.0.0.1:8766/")
    lines.append(f"• Public /: HTTP {public_root}")
    lines.append(f"• Public /login: HTTP {public_login}")
    lines.append(f"• Local /: HTTP {local_root}")

    ok_logs, logs = _run(["journalctl", "-n", "5", "-u", service, "--no-pager"])
    if ok_logs and logs:
        log_lines = logs.splitlines()[-2:]
        lines.append("")
        lines.append("Recent logs:")
        for line in log_lines:
            lines.append(f"  {line[-120:]}")

    return "\n".join(lines)


def _ops_status_view() -> str:
    service = "persgraph-web.service"
    lines = ["⚙️ PersGraph Status — Ops", ""]

    smoke = Path("/root/.openclaw/workspace/scratchpad/active/persgraph-smoke-test-2026-06-12.sh")
    if smoke.exists():
        ok_smoke, smoke_out = _run(["bash", str(smoke)], timeout=40)
        smoke_out = _strip_ansi(smoke_out)
        summary = "passed" if ok_smoke else "needs attention"
        lines.append(f"• Smoke test: {summary}")
        tail = [ln.strip() for ln in smoke_out.splitlines() if "Passed:" in ln or "Failed:" in ln or "All tests passed" in ln][-3:]
        for ln in tail:
            lines.append(f"  {ln}")
    else:
        lines.append("• Smoke test: script missing")

    ok_caddy, caddy = _run(["caddy", "validate", "--config", "/etc/caddy/Caddyfile"], timeout=20)
    lines.append(f"• Caddy config: {'valid' if ok_caddy else 'invalid'}")

    ok_git, git = _run(["git", "status", "--short"], timeout=15)
    if ok_git:
        dirty = "dirty" if git.strip() else "clean"
        lines.append(f"• Git working tree: {dirty}")

    ok_commit, commit = _run(["git", "rev-parse", "--short", "HEAD"], timeout=10)
    if ok_commit and commit:
        lines.append(f"• Current commit: {commit}")

    ok_active, active = _run(["systemctl", "is-active", service])
    lines.append(f"• Service restartable: {'yes' if ok_active and active == 'active' else 'check manually'}")

    ok_started, started = _run(["systemctl", "show", "-p", "ActiveEnterTimestamp", "--value", service])
    if ok_started and started:
        lines.append(f"• Last app restart: {started}")

    return "\n".join(lines)


def cmd_status(args: str = "") -> str:
    mode = (args or "").strip().lower()
    if mode == "service":
        return _service_status_view()
    if mode == "ops":
        return _ops_status_view()

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
        f"📬 Queue: {q['pending']} pending · {q['done']} done · {q['failed']} failed\n\n"
        f"Modes: /status service · /status ops"
    )


def cmd_debrief(args: str) -> str:
    import subprocess, sys, os
    period = args.strip() or "week"
    if period not in ("today", "week", "month"):
        return "❌ Usage: /debrief [today|week|month]"
    
    base_dir = os.path.join(os.path.dirname(__file__), "..")
    script = os.path.join(base_dir, "scripts", "debrief.py")
    
    try:
        result = subprocess.run(
            [sys.executable, script, period],
            capture_output=True, text=True, timeout=120,
            cwd=base_dir
        )
        if result.returncode == 0:
            return f"📊 Debrief generated for period: **{period}**\nView at: /debrief on your configured PersGraph host\n\n{result.stdout.strip()}"
        else:
            return f"❌ Debrief failed:\n{result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return "⏱ Debrief is taking longer than expected. Check /debrief on your configured PersGraph host in a minute."
    except Exception as e:
        return f"❌ Error: {e}"


def cmd_email(text: str) -> str:
    """Send an email on demand using the standalone SMTP script."""
    import shlex
    import subprocess
    import sys

    # Support a compact structured form:
    # /email to=person@example.com subject=Hello body=Hi there
    # and a simple fallback:
    # /email person@example.com | Subject | Body
    raw = text.strip()
    if not raw:
        return (
            "❌ Usage: /email to=<recipient> subject=<subject> body=<body>\n"
            "   or: /email <recipient> | <subject> | <body>"
        )

    to = subject = body = ""
    html = False

    # Parse key=value pairs first
    parts = shlex.split(raw)
    kv = {}
    leftovers = []
    for p in parts:
        if "=" in p and not p.startswith("http"):
            k, v = p.split("=", 1)
            kv[k.strip().lower()] = v.strip()
        else:
            leftovers.append(p)

    to = kv.get("to", "")
    subject = kv.get("subject", "")
    body = kv.get("body", "")
    html = kv.get("html", "false").lower() in {"1", "true", "yes", "y"}

    if not to and leftovers:
        joined = " ".join(leftovers)
        if "|" in joined:
            segs = [s.strip() for s in joined.split("|")]
            if len(segs) >= 3:
                to, subject, body = segs[0], segs[1], " | ".join(segs[2:])
        elif len(leftovers) >= 3:
            to, subject, body = leftovers[0], leftovers[1], " ".join(leftovers[2:])

    if not to or "@" not in to or not subject or not body:
        return (
            "❌ Usage: /email to=<recipient> subject=<subject> body=<body>\n"
            "   or: /email <recipient> | <subject> | <body>"
        )

    base_dir = Path(__file__).resolve().parent.parent
    script = base_dir / "scripts" / "send_email.py"
    cmd = [sys.executable, str(script), "--to", to, "--subject", subject, "--body", body]
    if html:
        cmd.append("--html")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=str(base_dir))
        if result.returncode == 0:
            return f"📨 Email sent to {to}\n{result.stdout.strip()}"
        return f"❌ Email failed:\n{result.stderr.strip() or result.stdout.strip()}"
    except subprocess.TimeoutExpired:
        return "⏱ Email send timed out"
    except Exception as e:
        return f"❌ Email error: {e}"


# Import learning layer outcome handlers
try:
    from second_brain.explore_outcome_handlers import (
        cmd_explore_accept,
        cmd_explore_click,
        cmd_explore_bookmark,
        cmd_explore_skip,
    )
    LEARNING_HANDLERS_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    LEARNING_HANDLERS_AVAILABLE = False

COMMANDS = {
    "/wiki-ingest": cmd_wiki_ingest,
    "/ingest":      cmd_ingest,
    "/ask":         cmd_ask,
    "/pghelp":      cmd_pghelp,
    "/note":        cmd_note,
    "/task":        cmd_task,
    "/place":       cmd_place,
    "/places":      cmd_places,
    "/bucketlist":  cmd_bucketlist,
    "/digest":      cmd_digest,
    "/email":       cmd_email,
    "/appointment": cmd_appointment,
    "/schedule":    cmd_schedule,
    "/TripToggle":  cmd_triptoggle,
    "/sport":       cmd_sport,
    "/debrief":     cmd_debrief,
}

# Learning layer outcome handlers (registered if available)
if LEARNING_HANDLERS_AVAILABLE:
    COMMANDS.update({
        "/explore_accept":   cmd_explore_accept,
        "/explore_click":    cmd_explore_click,
        "/explore_bookmark": cmd_explore_bookmark,
        "/explore_skip":     cmd_explore_skip,
    })

# Commands that accept a user context
USER_AWARE_COMMANDS = {"/ingest", "/ask"}


def run(raw_input: str, sender_id: str | None = None) -> str:
    raw_input = raw_input.strip()
    user = resolve_user(sender_id)
    # Map legacy model hints → LiteLLM virtual model tiers
    _model_raw = user.get("model", "haiku")
    _hint_map = {
        "haiku": "fast",
        "sonnet": "smart",
        "fast": "fast",
        "smart": "smart",
    }
    model_hint = _hint_map.get(_model_raw, "fast")

    # ── Langfuse trace (v4 API) ───────────────────────────────────────────────
    try:
        from second_brain.tracing import flush
        from second_brain.tracing import _ensure_env
        import os as _os
        _ensure_env()

        from langfuse import observe as lf_observe, Langfuse

        cmd_name = raw_input.split()[0] if raw_input else "unknown"
        start_ms = time.perf_counter()

        @lf_observe(name=cmd_name)
        def _traced_dispatch():
            res = _dispatch(raw_input, user)
            lf = Langfuse()
            lf.set_current_trace_io(input=raw_input, output=res[:800])
            return res

        result = _traced_dispatch()
        flush()
    except Exception:
        result = _dispatch(raw_input, user)
    # ─────────────────────────────────────────────────────────────────────────

    return f"MODEL_HINT: {model_hint}\n{result}"  # fast | smart → LiteLLM tiers


def _dispatch(raw_input: str, user: dict) -> str:
    raw_lower = raw_input.lower()
    # Sort longest-first so /places doesn't match before /place
    for cmd, handler in sorted(COMMANDS.items(), key=lambda x: -len(x[0])):
        cmd_lower = cmd.lower()
        if raw_lower.startswith(cmd_lower):
            args = raw_input[len(cmd):].strip()
            if cmd in USER_AWARE_COMMANDS:
                return handler(args, user=user)
            return handler(args)

    if raw_input.lower() == "/status":
        return cmd_status()
    if raw_input.lower().startswith("/status "):
        return cmd_status(raw_input[8:])

    return (
        "🤖 Unknown command.\n"
        "Use /pghelp for the full PersGraph command guide.\n"
        "Common commands: /ask, /note, /task, /place, /places, /appointment, /schedule, /status"
    )


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("Usage: python scripts/command.py [--sender <id>] '<command>'")
        sys.exit(1)

    # Parse optional --sender flag
    sender_id = None
    if len(args) >= 2 and args[0] == "--sender":
        sender_id = args[1]
        args = args[2:]

    print(run(" ".join(args), sender_id=sender_id))

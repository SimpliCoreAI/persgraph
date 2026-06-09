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
import json
import time
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

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


def cmd_ingest(args: str, user: dict | None = None) -> str:
    # Parse --user flag
    args, flag_user = _parse_user_flag(args)

    url = args.strip()
    if not url:
        return "❌ Usage: /ingest <url> [--user <name>]"

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
        if any(k in err.lower() for k in ["model", "ollama", "embed", "embedding", "404"]):
            enqueue_retry("url", {"url": url, "tags": tags}, needs=[DEP_OLLAMA, DEP_CHROMADB])
            return "⏳ Saved for retry\n🧠 Embedding backend not ready right now — will ingest automatically later\n🔗 {}".format(original_url)
        return f"❌ Ingestion failed: {err}"

    if result.success:
        return (
            "✅ Ingested!\n"
            f"📦 Collection: {result.collection}\n"
            f"✂️ Chunks: {result.chunks_new} new / {result.chunks_total} total\n"
            f"🏷️ Tags: {', '.join(result.tags) or 'none'}"
        )

    errors = '; '.join(result.errors)
    if any(k in errors.lower() for k in ["model", "ollama", "embed", "embedding", "404"]):
        enqueue_retry("url", {"url": url, "tags": tags}, needs=[DEP_OLLAMA, DEP_CHROMADB])
        return "⏳ Saved for retry\n🧠 Embedding backend not ready right now — will ingest automatically later\n🔗 {}".format(original_url)

    return f"❌ Ingestion failed: {errors}"

def cmd_ask(question: str, user: dict | None = None) -> str:
    """Retrieve relevant chunks from the brain. Claude synthesizes the answer."""
    question, flag_user = _parse_user_flag(question)

    if not question.strip():
        return "❌ Usage: /ask <question> [--user <name>]"

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


def cmd_sport(text: str) -> str:
    from second_brain.sports import get_sports_status
    return get_sports_status(text.strip())


def cmd_appointment(text: str) -> str:
    from second_brain.notes import save, list_all

    raw = text.strip()
    if not raw:
        return "❌ Usage: /appointment <title>, <date/time> or /appointment list"

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
    return f"✅ Appointment saved!\n📅 {title} — {_fmt_local(dt)}"


def cmd_reminder(text: str) -> str:
    import json
    import subprocess
    from datetime import timezone
    from second_brain.notes import save

    raw = text.strip()
    if not raw:
        return "❌ Usage: /reminder in 2h pick up kids"

    dt, title = _parse_datetime_loose(raw)
    if not dt or not title:
        return "❌ Usage: /reminder in 2h pick up kids | /reminder tomorrow 9am call dentist"

    save(title=title, item_type='Note', body=f'reminder_at:{dt.isoformat()}', date=dt.isoformat(), tags=['reminder'])

    iso_utc = dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    try:
        proc = subprocess.run(
            [
                'openclaw', 'gateway', 'cron', 'add', '--json',
                json.dumps({
                    'name': f'Reminder: {title[:60]}',
                    'schedule': {'kind': 'at', 'at': iso_utc},
                    'payload': {'kind': 'systemEvent', 'text': f'Reminder: {title}'},
                    'delivery': {'mode': 'announce', 'channel': 'telegram', 'to': 'telegram:8596241969'},
                    'sessionTarget': 'main',
                    'deleteAfterRun': True,
                })
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        cron_note = '\n🆔 Cron scheduled'
    except Exception:
        cron_note = '\n⚠️ Reminder saved, but cron scheduling failed.'

    return (
        f"✅ Reminder set!\n"
        f"⏰ {title} — {_fmt_local(dt)}"
        f"{cron_note}"
    )


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

    items.sort(key=lambda x: x[0])
    label = 'Next 7 days' if mode == 'week' else 'Today'
    if not items:
        return f"📅 Schedule — {label}\n\n• Nothing scheduled"

    lines = [f"📅 Schedule — {label}", ""]
    for dt, kind, title in items[:20]:
        lines.append(f"• {_fmt_local(dt)} — {title} [{kind}]")
    return '\n'.join(lines)


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
            return f"📊 Debrief generated for period: **{period}**\nView at: http://5.78.196.42:8766/debrief\n\n{result.stdout.strip()}"
        else:
            return f"❌ Debrief failed:\n{result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return "⏱ Debrief is taking longer than expected. Check http://5.78.196.42:8766/debrief in a minute."
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


COMMANDS = {
    "/wiki-ingest": cmd_wiki_ingest,
    "/ingest":      cmd_ingest,
    "/ask":         cmd_ask,
    "/note":        cmd_note,
    "/task":        cmd_task,
    "/place":       cmd_place,
    "/places":      cmd_places,
    "/email":       cmd_email,
    "/appointment": cmd_appointment,
    "/reminder":    cmd_reminder,
    "/schedule":    cmd_schedule,
    "/sport":       cmd_sport,
    "/debrief":     cmd_debrief,
}

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
    # Sort longest-first so /places doesn't match before /place
    for cmd, handler in sorted(COMMANDS.items(), key=lambda x: -len(x[0])):
        if raw_input.lower().startswith(cmd):
            args = raw_input[len(cmd):].strip()
            if cmd in USER_AWARE_COMMANDS:
                return handler(args, user=user)
            return handler(args)

    if raw_input.lower() == "/status":
        return cmd_status()

    return (
        "🤖 Unknown command. Available:\n"
        "  /wiki-ingest <url>              — write curated Obsidian wiki note, then index it\n"
        "  /ingest <url> [--user <name>]   — raw URL ingest for semantic search\n"
        "  /ask <question> [--user <name>] — query the brain\n"
        "  /note <text>                    — save a note\n"
        "  /task <text>                    — save a task\n"
        "  /place <name>, <city> [, notes] — save a place (instant)\n"
        "  /places [city]                  — list saved places\n"
        "  /appointment <title>, <date/time> | list — save/list appointments\n"
        "  /reminder <time> <text>         — save reminder intent\n"
        "  /schedule [week]                — show upcoming schedule\n"
        "  /sport [soccer|football|nba] — sports schedule\n"
        "  /debrief [today|week|month]     — generate activity debrief\n"
        "  /status                         — collection + queue stats"
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

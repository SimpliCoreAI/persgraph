#!/usr/bin/env python3
"""
Email worker — polls the openclaw Gmail inbox, classifies intent,
routes each email to the right handler, then confirms via Telegram output.

Called by OpenClaw cron every 30 minutes.

Output protocol (stdout):
  - Regular lines: progress/info
  - Lines starting with CONFIRM: → Telegram confirmation messages
  - Lines starting with CLARIFY_JSON: → JSON blob for Telegram button prompt
  - Lines starting with ERROR: → errors to surface

Exit codes: 0 = success (even if 0 emails), 1 = fatal error
"""

import sys
import os
import json
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from second_brain.ingesters.email import (
    EmailIngester,
    ParsedEmail,
    INTENT_TASK,
    INTENT_APPOINTMENT,
    INTENT_NOTE,
    INTENT_URL,
    INTENT_UNKNOWN,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Handlers ──────────────────────────────────────────────────────────────────

def handle_task(email: ParsedEmail) -> str:
    """Save as task to ChromaDB notes collection."""
    from second_brain.notes import save
    result = save(
        title=email.clean_subject,
        item_type="Task",
        body="",  # skip body — subject only
        date=email.date_hint,
        tags=["email", "task"],
    )
    return f"✅ Task saved: {result['title']}"


def handle_appointment(email: ParsedEmail) -> str:
    """
    Save appointment to ChromaDB AND create Google Calendar event via gog.
    Calendar creation is best-effort — ChromaDB save always happens.
    """
    from second_brain.notes import save

    # 1. Save to ChromaDB
    result = save(
        title=email.clean_subject,
        item_type="Appointment",
        body="",  # skip body — subject only
        date=email.date_hint,
        tags=["email", "appointment"],
    )

    # 2. Try Google Calendar via gog CLI
    cal_status = _create_calendar_event(email)

    return f"📅 Appointment saved: {result['title']}{cal_status}"


def _create_calendar_event(email: ParsedEmail) -> str:
    """
    Parse date/time from email and create a Google Calendar event.
    Returns status string (empty if failed).

    Uses a quick LLM call to extract structured datetime from free-form text.
    """
    import subprocess
    from second_brain.config import settings

    # Extract structured datetime via LLM
    event_json = _extract_event_details(email.clean_subject, email.body)
    if not event_json:
        return "\n⚠️ Couldn't parse date — not added to Calendar. Reply with date to add manually."

    summary = event_json.get("summary", email.clean_subject)
    start_iso = event_json.get("start")  # e.g. "2026-06-05T15:00:00"
    end_iso = event_json.get("end")      # e.g. "2026-06-05T16:00:00"
    description = event_json.get("description", email.body[:200])

    if not start_iso:
        return "\n⚠️ No date found — not added to Calendar."

    try:
        gog_account = settings.gog_account
        cmd = [
            "gog", "calendar", "create", "primary",
            "--summary", summary,
            "--from", start_iso,
            "--to", end_iso or start_iso,
            "--description", description,
            "--account", gog_account,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            return "\n📆 Added to Google Calendar ✓"
        else:
            return f"\n⚠️ Calendar add failed: {result.stderr.strip()[:100]}"
    except Exception as e:
        return f"\n⚠️ Calendar error: {str(e)[:80]}"


def _extract_event_details(subject: str, body: str) -> dict | None:
    """Use Anthropic to extract structured event details from free-form text."""
    try:
        import anthropic
        from second_brain.config import settings

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        today = datetime.now().strftime("%Y-%m-%d")

        prompt = f"""Extract calendar event details from this email. Today is {today}.

Subject: {subject}
Body: {body[:500]}

Return ONLY valid JSON with these fields (no markdown, no explanation):
{{
  "summary": "event title",
  "start": "YYYY-MM-DDTHH:MM:SS",
  "end": "YYYY-MM-DDTHH:MM:SS",
  "description": "brief description"
}}

If no specific date/time found, return: {{"summary": null, "start": null, "end": null, "description": null}}"""

        message = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )

        text = message.content[0].text.strip()
        # Strip markdown code fences if present
        text = text.strip("`").strip()
        if text.startswith("json"):
            text = text[4:].strip()

        data = json.loads(text)
        if not data.get("start"):
            return None
        return data
    except Exception:
        return None


def handle_url(email: ParsedEmail) -> str:
    """Ingest URL(s) from email."""
    from second_brain.ingesters.url import URLIngester

    ingester = URLIngester()
    results = []

    urls = email.urls or []
    # Also check clean_subject for bare URLs
    if not urls and email.clean_subject.startswith("http"):
        urls = [email.clean_subject]

    if not urls:
        # Fall back to note
        return handle_note(email) + " (no URL found, saved as note)"

    for url in urls[:3]:  # cap at 3 URLs per email
        try:
            result = ingester.ingest(url, tags=["email"])
            if result.success:
                results.append(f"🌐 {url[:60]} · {result.chunks_new} chunks")
            else:
                results.append(f"⚠️ {url[:60]}: {', '.join(result.errors)}")
        except Exception as e:
            results.append(f"⚠️ {url[:60]}: {str(e)[:60]}")

    return "\n".join(results) if results else "⚠️ No URLs processed"


def handle_note(email: ParsedEmail) -> str:
    """Save as general note to ChromaDB."""
    from second_brain.notes import save
    result = save(
        title=email.clean_subject,
        item_type="Note",
        body="",  # skip body — subject only
        tags=["email"],
    )
    return f"📝 Note saved: {result['title']}"


HANDLERS = {
    INTENT_TASK:        handle_task,
    INTENT_APPOINTMENT: handle_appointment,
    INTENT_NOTE:        handle_note,
    INTENT_URL:         handle_url,
}

INTENT_EMOJI = {
    INTENT_TASK:        "✅",
    INTENT_APPOINTMENT: "📅",
    INTENT_NOTE:        "📝",
    INTENT_URL:         "🌐",
}

INTENT_LABEL = {
    INTENT_TASK:        "Task",
    INTENT_APPOINTMENT: "Appointment",
    INTENT_NOTE:        "Note",
    INTENT_URL:         "URL / Link",
}


# ── Clarification output ──────────────────────────────────────────────────────

def emit_clarification(email: ParsedEmail) -> None:
    """
    Emit a CLARIFY_JSON line so OpenClaw can ask Jolly via Telegram buttons.
    The email is NOT marked read until Jolly responds.
    """
    payload = {
        "uid": email.uid,
        "subject": email.clean_subject,
        "sender": email.sender,
        "body_preview": email.body[:150],
        "question": f'How should I file this email?\n\n📧 "{email.clean_subject}"',
        "buttons": [
            {"label": "✅ Task",        "value": INTENT_TASK},
            {"label": "📅 Appointment", "value": INTENT_APPOINTMENT},
            {"label": "📝 Note",        "value": INTENT_NOTE},
            {"label": "🌐 URL",         "value": INTENT_URL},
            {"label": "🗑️ Ignore",      "value": "ignore"},
        ],
    }
    print(f"CLARIFY_JSON:{json.dumps(payload)}")


# ── Main ──────────────────────────────────────────────────────────────────────

def run() -> list[dict]:
    """
    Fetch and process unread emails. Returns list of result dicts.
    Prints CONFIRM: and CLARIFY_JSON: lines for OpenClaw to act on.
    """
    ingester = EmailIngester()

    try:
        emails = ingester.fetch_unread()
    except Exception as e:
        print(f"ERROR:Failed to connect to inbox: {e}")
        return []

    if not emails:
        return []

    results = []

    for em in emails:
        if em.needs_clarification or em.intent == INTENT_UNKNOWN:
            emit_clarification(em)
            results.append({"uid": em.uid, "status": "pending_clarification"})
            continue

        handler = HANDLERS.get(em.intent, handle_note)

        try:
            detail = handler(em)
            ingester.mark_read(em.uid)

            emoji = INTENT_EMOJI.get(em.intent, "📧")
            label = INTENT_LABEL.get(em.intent, "Item")

            confirm_msg = (
                f"📧 Email ingested\n"
                f"Type: {label}\n"
                f"{emoji} \"{em.clean_subject}\"\n"
                f"From: {em.sender}\n"
                f"{detail}"
            )
            print(f"CONFIRM:{confirm_msg}")

            results.append({
                "uid": em.uid,
                "intent": em.intent,
                "subject": em.clean_subject,
                "status": "processed",
            })

        except Exception as e:
            err_msg = f"⚠️ Failed to process email \"{em.clean_subject}\": {str(e)}"
            print(f"ERROR:{err_msg}")
            results.append({
                "uid": em.uid,
                "status": "failed",
                "error": str(e),
            })

    return results


if __name__ == "__main__":
    results = run()
    if results:
        processed = [r for r in results if r.get("status") == "processed"]
        pending   = [r for r in results if r.get("status") == "pending_clarification"]
        failed    = [r for r in results if r.get("status") == "failed"]
        print(
            f"\n── Email worker done: "
            f"{len(processed)} processed, "
            f"{len(pending)} need clarification, "
            f"{len(failed)} failed ──"
        )

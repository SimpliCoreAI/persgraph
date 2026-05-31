"""
Email ingester — polls Gmail IMAP, classifies intent, routes to handlers.

Flow:
  1. Connect to Gmail via IMAP (App Password in .env)
  2. Fetch unread emails from trusted senders only
  3. Parse subject prefix → deterministic routing
     No prefix → LLM classifies → ask Telegram if still unsure
  4. Return ParsedEmail list for email_worker.py to action
"""

from __future__ import annotations

import email
import imaplib
import re
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.header import decode_header
from typing import Optional
from urllib.parse import urlparse

from ..config import settings


# ── Trusted senders ───────────────────────────────────────────────────────────
# Set TRUSTED_SENDERS in .env as a comma-separated list:
#   TRUSTED_SENDERS=you@gmail.com,other@yahoo.com

import os as _os
_raw = _os.getenv("TRUSTED_SENDERS", "")
TRUSTED_SENDERS: set[str] = {
    e.strip().lower() for e in _raw.split(",") if e.strip()
}

# ── Intent types ──────────────────────────────────────────────────────────────

INTENT_TASK        = "task"
INTENT_APPOINTMENT = "appointment"
INTENT_NOTE        = "note"
INTENT_URL         = "url"
INTENT_UNKNOWN     = "unknown"  # triggers Telegram clarification

# ── Subject prefix map ────────────────────────────────────────────────────────

PREFIX_MAP = {
    "TASK":  INTENT_TASK,
    "TODO":  INTENT_TASK,
    "APPT":  INTENT_APPOINTMENT,
    "CAL":   INTENT_APPOINTMENT,
    "NOTE":  INTENT_NOTE,
    "URL":   INTENT_URL,
    "LINK":  INTENT_URL,
}

# Regex: optional prefix at start of subject
_PREFIX_RE = re.compile(r"^(TASK|TODO|APPT|CAL|NOTE|URL|LINK)\s*[:\-]\s*", re.IGNORECASE)

# Simple URL detector
_URL_RE = re.compile(r"https?://[^\s]+")


@dataclass
class ParsedEmail:
    uid: str
    sender: str
    subject: str
    body: str
    intent: str                    # one of INTENT_* constants
    clean_subject: str             # subject with prefix stripped
    urls: list[str] = field(default_factory=list)
    date_hint: Optional[str] = None   # extracted date string if any
    raw_date: Optional[str] = None
    needs_clarification: bool = False


class EmailIngester:
    """Fetch and classify unread emails from the openclaw Gmail inbox."""

    def __init__(self) -> None:
        self.imap_host = "imap.gmail.com"
        self.imap_port = 993
        self.email_address = settings.openclaw_email
        self.app_password = settings.openclaw_email_password

    # ── Public API ────────────────────────────────────────────────────────────

    def fetch_unread(self) -> list[ParsedEmail]:
        """Connect, fetch unread emails from trusted senders, return ParsedEmail list."""
        results = []

        with self._connect() as conn:
            conn.select("INBOX")
            uids = self._search_unread(conn)

            for uid in uids:
                raw = self._fetch_raw(conn, uid)
                if not raw:
                    continue

                msg = email.message_from_bytes(raw)
                sender = self._parse_sender(msg)

                if not self._is_trusted(sender):
                    continue  # silently skip

                parsed = self._parse_message(uid.decode(), sender, msg)
                results.append(parsed)

        return results

    def mark_read(self, uid: str) -> None:
        """Mark a single email as read after successful processing."""
        with self._connect() as conn:
            conn.select("INBOX")
            conn.uid("STORE", uid.encode(), "+FLAGS", "\\Seen")

    # ── IMAP helpers ─────────────────────────────────────────────────────────

    def _connect(self) -> imaplib.IMAP4_SSL:
        conn = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
        conn.login(self.email_address, self.app_password)
        return conn

    def _search_unread(self, conn: imaplib.IMAP4_SSL) -> list[bytes]:
        status, data = conn.uid("SEARCH", None, "UNSEEN")
        if status != "OK" or not data[0]:
            return []
        return data[0].split()

    def _fetch_raw(self, conn: imaplib.IMAP4_SSL, uid: bytes) -> Optional[bytes]:
        status, data = conn.uid("FETCH", uid, "(RFC822)")
        if status != "OK" or not data or not data[0]:
            return None
        return data[0][1]

    # ── Parsing ───────────────────────────────────────────────────────────────

    def _parse_sender(self, msg: email.message.Message) -> str:
        raw_from = msg.get("From", "")
        # Extract email address from "Name <email>" format
        match = re.search(r"<([^>]+)>", raw_from)
        if match:
            return match.group(1).lower().strip()
        return raw_from.lower().strip()

    def _is_trusted(self, sender: str) -> bool:
        return sender in TRUSTED_SENDERS

    def _decode_header_value(self, value: str) -> str:
        parts = decode_header(value)
        decoded = []
        for part, charset in parts:
            if isinstance(part, bytes):
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                decoded.append(part)
        return " ".join(decoded)

    def _extract_body(self, msg: email.message.Message) -> str:
        """Extract plain text body from email."""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    charset = part.get_content_charset() or "utf-8"
                    body = part.get_payload(decode=True).decode(charset, errors="replace")
                    break
        else:
            if msg.get_content_type() == "text/plain":
                charset = msg.get_content_charset() or "utf-8"
                body = msg.get_payload(decode=True).decode(charset, errors="replace")
        return body.strip()

    def _extract_urls(self, text: str) -> list[str]:
        return _URL_RE.findall(text)

    def _parse_message(
        self,
        uid: str,
        sender: str,
        msg: email.message.Message,
    ) -> ParsedEmail:
        raw_subject = self._decode_header_value(msg.get("Subject", ""))
        body = self._extract_body(msg)
        raw_date = msg.get("Date", "")

        # Strip prefix
        prefix_match = _PREFIX_RE.match(raw_subject)
        if prefix_match:
            prefix = prefix_match.group(1).upper()
            intent = PREFIX_MAP[prefix]
            clean_subject = raw_subject[prefix_match.end():].strip()
            needs_clarification = False
        else:
            clean_subject = raw_subject.strip()
            intent, needs_clarification = self._classify_intent(raw_subject, body)

        # Extract URLs from subject + body
        urls = self._extract_urls(raw_subject + " " + body)

        # If intent is URL and we have a URL, use first one as primary
        if intent == INTENT_URL and not urls:
            intent = INTENT_NOTE  # fallback if labeled URL but no link found

        return ParsedEmail(
            uid=uid,
            sender=sender,
            subject=raw_subject,
            body=body,
            intent=intent,
            clean_subject=clean_subject,
            urls=urls,
            raw_date=raw_date,
            needs_clarification=needs_clarification,
        )

    # ── Intent classification (no-prefix fallback) ────────────────────────────

    def _classify_intent(self, subject: str, body: str) -> tuple[str, bool]:
        """
        Classify email intent using heuristics first, LLM second.
        Returns (intent, needs_clarification).
        """
        combined = (subject + " " + body).lower()

        # Heuristic: URL only
        urls = _URL_RE.findall(subject + " " + body)
        if urls and len(combined.split()) < 20:
            return INTENT_URL, False

        # Heuristic: appointment keywords
        appt_keywords = [
            "appointment", "meeting", "call", "dentist", "doctor",
            "interview", "lunch", "dinner", "session", "at ", "pm", "am",
            "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug",
            "sep", "oct", "nov", "dec", "monday", "tuesday", "wednesday",
            "thursday", "friday", "saturday", "sunday",
        ]
        appt_score = sum(1 for kw in appt_keywords if kw in combined)

        # Heuristic: task keywords
        task_keywords = [
            "remind", "remember", "todo", "don't forget", "follow up",
            "call", "email", "book", "schedule", "buy", "check", "find",
            "research", "look into", "need to",
        ]
        task_score = sum(1 for kw in task_keywords if kw in combined)

        if appt_score >= 3:
            return INTENT_APPOINTMENT, False
        if task_score >= 2:
            return INTENT_TASK, False

        # Try LLM if Anthropic key available
        try:
            return self._classify_with_llm(subject, body)
        except Exception:
            pass

        # Fallback: ask user
        return INTENT_UNKNOWN, True

    def _classify_with_llm(self, subject: str, body: str) -> tuple[str, bool]:
        """Use Anthropic to classify intent. Returns (intent, needs_clarification)."""
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        prompt = f"""Classify this email into exactly one category: task, appointment, note, url.

Subject: {subject}
Body: {body[:500]}

Rules:
- appointment: has a specific date/time and event (meeting, call, medical, etc.)
- task: something to do/remember, no specific date-time
- url: primarily a link to save/read later
- note: general information to remember

Reply with ONLY one word: task, appointment, note, or url"""

        message = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )

        intent_raw = message.content[0].text.strip().lower()
        intent_map = {
            "task": INTENT_TASK,
            "appointment": INTENT_APPOINTMENT,
            "note": INTENT_NOTE,
            "url": INTENT_URL,
        }
        intent = intent_map.get(intent_raw, INTENT_UNKNOWN)
        needs_clarification = intent == INTENT_UNKNOWN
        return intent, needs_clarification

from __future__ import annotations

import json
from pathlib import Path

from .schemas import CalendarEvent, InboxEmail


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "prebrief"


def load_fixture_events() -> list[CalendarEvent]:
    data = json.loads((FIXTURE_DIR / "events.json").read_text())
    return [CalendarEvent.from_dict(item) for item in data]


def load_fixture_emails() -> list[InboxEmail]:
    data = json.loads((FIXTURE_DIR / "emails.json").read_text())
    return [InboxEmail.from_dict(item) for item in data]

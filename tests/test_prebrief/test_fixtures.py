import json
from pathlib import Path

from second_brain.connectors.schemas import CalendarEvent, DailyContext, InboxEmail

ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "prebrief"


def test_events_fixture_loads():
    data = json.loads((ROOT / "events.json").read_text())
    events = [CalendarEvent.from_dict(item) for item in data]
    assert len(events) == 3
    assert events[1].category == "family"


def test_emails_fixture_loads():
    data = json.loads((ROOT / "emails.json").read_text())
    emails = [InboxEmail.from_dict(item) for item in data]
    assert len(emails) == 4
    assert emails[0].bucket == "bill"
    assert emails[0].amount == 142.5


def test_daily_context_fixture_loads():
    raw = (ROOT / "daily_context.json").read_text()
    context = DailyContext.from_json(raw)
    assert context.date.isoformat() == "2026-06-15"
    assert context.events_today.items[0]["id"] == "evt_001"
    assert context.suggested_priorities[0] == "Review bill due June 18"


def test_fixtures_use_only_synthetic_domains():
    combined = "\n".join((ROOT / name).read_text() for name in ["events.json", "emails.json", "daily_context.json"])
    assert "@gmail.com" not in combined
    assert "@yahoo.com" not in combined
    assert ".example" in combined or ".test" in combined

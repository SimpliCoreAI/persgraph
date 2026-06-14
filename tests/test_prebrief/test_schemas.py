import json
from datetime import date, datetime

from second_brain.connectors.schemas import CalendarEvent, DailyContext, InboxEmail, PreBriefSection


def test_calendar_event_roundtrip():
    event = CalendarEvent(
        id="evt_001",
        source="fixture",
        title="Dentist appointment",
        start_time=datetime.fromisoformat("2026-06-15T14:00:00"),
        end_time=datetime.fromisoformat("2026-06-15T15:00:00"),
        participants=["Sam Rivera"],
        location="123 Main St",
        notes="Bring insurance card",
        category="personal",
        prep_needed=True,
    )
    restored = CalendarEvent.from_dict(event.to_dict())
    assert restored == event


def test_inbox_email_roundtrip():
    email = InboxEmail(
        id="email_001",
        source="fixture",
        sender="billing@fakebank.example",
        subject="Your statement is ready — due June 18",
        timestamp=datetime.fromisoformat("2026-06-14T08:00:00+00:00"),
        snippet="Payment due June 18. Amount: $142.50.",
        labels=["billing"],
        bucket="bill",
        due_date=date.fromisoformat("2026-06-18"),
        amount=142.5,
        urgency=2,
        confidence=0.95,
        action_required=True,
        thread_key="t_fakebank_statement",
        source_ref="uid://email_001",
    )
    restored = InboxEmail.from_dict(email.to_dict())
    assert restored == email


def test_prebrief_section_roundtrip():
    section = PreBriefSection(items=[{"id": "x1", "title": "Sample"}], capped=False, cap_limit=5)
    restored = PreBriefSection.from_dict(section.to_dict())
    assert restored == section


def test_daily_context_roundtrip_json():
    context = DailyContext(
        date=date.fromisoformat("2026-06-15"),
        generated_at=datetime.fromisoformat("2026-06-15T07:00:00+00:00"),
        events_today=PreBriefSection(items=[{"id": "evt_001"}], capped=False, cap_limit=5),
        events_upcoming=PreBriefSection(items=[{"id": "evt_003"}], capped=False, cap_limit=5),
        bills_due=PreBriefSection(items=[{"id": "email_001"}], capped=False, cap_limit=5),
        followups_needed=PreBriefSection(items=[{"id": "email_002"}], capped=False, cap_limit=5),
        worth_checking=PreBriefSection(items=[{"id": "email_003"}], capped=False, cap_limit=5),
        carry_forward=PreBriefSection(items=[], capped=False, cap_limit=5),
        suggested_priorities=["Review bill", "Handle follow-up"],
    )
    restored = DailyContext.from_json(context.to_json())
    assert restored == context


def test_daily_context_dict_is_json_serializable():
    context = DailyContext(
        date=date.fromisoformat("2026-06-15"),
        generated_at=datetime.fromisoformat("2026-06-15T07:00:00+00:00"),
        events_today=PreBriefSection(items=[], capped=False, cap_limit=5),
        events_upcoming=PreBriefSection(items=[], capped=False, cap_limit=5),
        bills_due=PreBriefSection(items=[], capped=False, cap_limit=5),
        followups_needed=PreBriefSection(items=[], capped=False, cap_limit=5),
        worth_checking=PreBriefSection(items=[], capped=False, cap_limit=5),
        carry_forward=PreBriefSection(items=[], capped=False, cap_limit=5),
        suggested_priorities=[],
    )
    payload = context.to_dict()
    assert json.loads(json.dumps(payload))["date"] == "2026-06-15"

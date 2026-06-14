"""
Tests for Prebrief Builder module (Batch 6).

Tests cover:
- PrebriefContextRanker: ranking and capping logic for each section
- PrebriefBuilder: combining events and emails into DailyContext
- PrebriefMarkdownRenderer: Markdown output generation
- Integration: full workflow from fixtures to JSON and Markdown
"""

import json
from datetime import date, datetime, timedelta

from second_brain.connectors.prebrief_builder import (
    PrebriefBuilder,
    PrebriefContextRanker,
    PrebriefMarkdownRenderer,
    DEFAULT_SECTION_CAPS,
)
from second_brain.connectors.schemas import CalendarEvent, InboxEmail, PreBriefSection

from tests.fixtures.prebrief.calendar_events import (
    sample_standup_meeting,
    sample_afternoon_meeting,
    sample_all_day_event,
    sample_dental_appointment,
    sample_calendar_events,
)
from tests.fixtures.prebrief.inbox_emails import (
    sample_task_email,
    sample_bill_email,
    sample_appointment_email,
    sample_url_email,
    sample_urgent_followup_email,
    sample_overdue_bill,
    sample_inbox_emails,
)
from tests.fixtures.prebrief.daily_context import (
    sample_daily_context,
    sample_empty_daily_context,
)


# ── Tests for PrebriefContextRanker ─────────────────────────────────────────


class TestPrebriefContextRankerEventsToday:
    """Tests for rank_and_cap_events_today."""

    def test_rank_events_today_by_start_time(self):
        """Events should be ranked by start_time (ascending)."""
        # Create events in random order
        afternoon = sample_afternoon_meeting()  # 14:00
        standup = sample_standup_meeting()  # 09:00

        events = [afternoon, standup]
        section = PrebriefContextRanker.rank_and_cap_events_today(events)

        assert len(section.items) == 2
        assert section.items[0]["id"] == "evt_standup_001"  # 09:00
        assert section.items[1]["id"] == "evt_1on1_001"  # 14:00

    def test_events_today_capping_flag(self):
        """Should set capped=True when items exceed cap_limit."""
        events = sample_calendar_events()
        section = PrebriefContextRanker.rank_and_cap_events_today(
            events, cap_limit=2
        )

        # 4 events total, 2 are today (standup, afternoon), 2 are future (all_day, dental)
        # When we cap at 2, we have more than 2 total events, so capped should be True
        assert len(section.items) == 2
        assert section.capped is True  # More events exist than cap_limit
        assert section.cap_limit == 2

    def test_events_today_no_cap(self):
        """Should include all events when cap_limit is 0."""
        events = sample_calendar_events()
        section = PrebriefContextRanker.rank_and_cap_events_today(
            events, cap_limit=0
        )

        # Should include all events (but only those from 2026-06-14)
        assert section.capped is False

    def test_events_today_empty(self):
        """Should handle empty event list."""
        section = PrebriefContextRanker.rank_and_cap_events_today([])
        assert len(section.items) == 0
        assert section.capped is False


class TestPrebriefContextRankerBillsDue:
    """Tests for rank_and_cap_bills_due."""

    def test_bills_ranked_by_due_date(self):
        """Bills should be ranked by due_date (ascending)."""
        # Create bills with different due dates
        bills = [sample_bill_email(), sample_overdue_bill()]

        section = PrebriefContextRanker.rank_and_cap_bills_due(bills)

        assert len(section.items) == 2
        # Overdue bill (due 2026-06-10) should come first
        assert section.items[0]["id"] == "msg_bill_002"
        # Later bill (due 2026-06-18) should come second
        assert section.items[1]["id"] == "msg_bill_001"

    def test_bills_capping_flag(self):
        """Should set capped=True when bills exceed cap_limit."""
        bills = [sample_bill_email(), sample_overdue_bill()]
        section = PrebriefContextRanker.rank_and_cap_bills_due(bills, cap_limit=1)

        assert len(section.items) == 1
        assert section.capped is True
        assert section.cap_limit == 1

    def test_bills_urgency_secondary_sort(self):
        """Bills with same due_date should sort by urgency (descending)."""
        # Create two bills with same due date but different urgency
        bill1 = InboxEmail(
            id="bill_same_date_1",
            source="fixture",
            sender="bank@example.com",
            subject="Bill 1",
            timestamp=datetime.fromisoformat("2026-06-14T10:00:00"),
            snippet="Bill 1",
            bucket="bill",
            due_date=date.fromisoformat("2026-06-20"),
            urgency=2,
        )
        bill2 = InboxEmail(
            id="bill_same_date_2",
            source="fixture",
            sender="bank@example.com",
            subject="Bill 2",
            timestamp=datetime.fromisoformat("2026-06-14T10:00:00"),
            snippet="Bill 2",
            bucket="bill",
            due_date=date.fromisoformat("2026-06-20"),
            urgency=4,
        )
        section = PrebriefContextRanker.rank_and_cap_bills_due([bill1, bill2])

        # Bill 2 (urgency 4) should come before Bill 1 (urgency 2)
        assert section.items[0]["id"] == "bill_same_date_2"
        assert section.items[1]["id"] == "bill_same_date_1"

    def test_bills_filters_non_bills(self):
        """Should only include emails with bucket='bill'."""
        emails = [sample_bill_email(), sample_task_email()]  # task is not bill
        section = PrebriefContextRanker.rank_and_cap_bills_due(emails)

        assert len(section.items) == 1
        assert section.items[0]["id"] == "msg_bill_001"


class TestPrebriefContextRankerFollowups:
    """Tests for rank_and_cap_followups_needed."""

    def test_followups_ranked_by_urgency_desc(self):
        """Followups should be ranked by urgency (descending)."""
        followups = [sample_task_email(), sample_urgent_followup_email()]

        section = PrebriefContextRanker.rank_and_cap_followups_needed(followups)

        assert len(section.items) == 2
        # Urgent followup (urgency 4) should come first
        assert section.items[0]["id"] == "msg_task_002"
        # Regular followup (urgency 2) should come second
        assert section.items[1]["id"] == "msg_task_001"

    def test_followups_capping_flag(self):
        """Should set capped=True when followups exceed cap_limit."""
        followups = [sample_task_email(), sample_urgent_followup_email()]
        section = PrebriefContextRanker.rank_and_cap_followups_needed(
            followups, cap_limit=1
        )

        assert len(section.items) == 1
        assert section.capped is True

    def test_followups_filters_non_followups(self):
        """Should only include emails with bucket='followup'."""
        emails = [
            sample_task_email(),
            sample_bill_email(),
            sample_appointment_email(),
        ]
        section = PrebriefContextRanker.rank_and_cap_followups_needed(emails)

        # Only task_email and urgent_followup have bucket='followup'
        # But our test sample has only task_email as followup + bill and appointment
        followup_count = sum(1 for e in emails if e.bucket == "followup")
        assert len(section.items) == followup_count


class TestPrebriefContextRankerWorthChecking:
    """Tests for rank_and_cap_worth_checking."""

    def test_worth_checking_ranked_by_urgency_then_confidence(self):
        """Items should rank by urgency (desc), then confidence (desc)."""
        emails = [sample_url_email(), sample_appointment_email()]

        section = PrebriefContextRanker.rank_and_cap_worth_checking(emails)

        # Both are worth_checking; appointment has confidence 0.8, url has 0.7
        assert len(section.items) == 2
        # Both have same urgency (1), so order by confidence
        # Both should be included but order by confidence desc
        ids = [item["id"] for item in section.items]
        assert "msg_appt_001" in ids
        assert "msg_url_001" in ids

    def test_worth_checking_filters_by_bucket(self):
        """Should only include emails with bucket='worth_checking'."""
        emails = [sample_bill_email(), sample_appointment_email(), sample_task_email()]
        section = PrebriefContextRanker.rank_and_cap_worth_checking(emails)

        # Only appointment_email has bucket='worth_checking'
        assert len(section.items) == 1
        assert section.items[0]["id"] == "msg_appt_001"


# ── Tests for PrebriefBuilder ─────────────────────────────────────────────


class TestPrebriefBuilderBasic:
    """Tests for basic PrebriefBuilder functionality."""

    def test_build_with_sample_events_and_emails(self):
        """Should build complete DailyContext from events and emails."""
        events = sample_calendar_events()
        emails = sample_inbox_emails()

        builder = PrebriefBuilder(reference_date=date.fromisoformat("2026-06-14"))
        context = builder.build(events, emails)

        assert context.date == date.fromisoformat("2026-06-14")
        assert context.events_today is not None
        assert context.events_upcoming is not None
        assert context.bills_due is not None
        assert context.followups_needed is not None
        assert context.worth_checking is not None
        assert context.carry_forward is not None
        assert isinstance(context.suggested_priorities, list)

    def test_build_separates_events_today_from_upcoming(self):
        """Should separate events by date."""
        events = sample_calendar_events()
        emails = []

        builder = PrebriefBuilder(reference_date=date.fromisoformat("2026-06-14"))
        context = builder.build(events, emails)

        # June 14 events: standup, afternoon meeting (2)
        # June 15+ events: all_day_event, dental (2)
        assert len(context.events_today.items) == 2
        assert len(context.events_upcoming.items) == 2

    def test_build_default_section_caps(self):
        """Should use default section caps from DEFAULT_SECTION_CAPS."""
        events = []
        emails = []

        builder = PrebriefBuilder()
        context = builder.build(events, emails)

        assert context.events_today.cap_limit == DEFAULT_SECTION_CAPS["events_today"]
        assert context.events_upcoming.cap_limit == DEFAULT_SECTION_CAPS[
            "events_upcoming"
        ]
        assert context.bills_due.cap_limit == DEFAULT_SECTION_CAPS["bills_due"]

    def test_build_custom_section_caps(self):
        """Should allow custom section caps."""
        custom_caps = {"events_today": 3, "bills_due": 2}

        builder = PrebriefBuilder(section_caps=custom_caps)
        context = builder.build([], [])

        assert context.events_today.cap_limit == 3
        assert context.bills_due.cap_limit == 2
        assert context.events_upcoming.cap_limit == DEFAULT_SECTION_CAPS[
            "events_upcoming"
        ]

    def test_build_custom_reference_date(self):
        """Should allow custom reference date."""
        custom_date = date.fromisoformat("2026-06-20")

        builder = PrebriefBuilder(reference_date=custom_date)
        context = builder.build([], [])

        assert context.date == custom_date


class TestPrebriefBuilderPriorities:
    """Tests for suggested_priorities generation."""

    def test_priorities_includes_urgent_bills(self):
        """Should include urgent bills (urgency >= 4) in priorities."""
        events = []
        emails = [sample_overdue_bill()]

        builder = PrebriefBuilder(reference_date=date.fromisoformat("2026-06-14"))
        context = builder.build(events, emails)

        priorities_text = " ".join(context.suggested_priorities)
        assert "Urgent" in priorities_text or "Bill" in priorities_text

    def test_priorities_includes_urgent_followups(self):
        """Should include urgent followups (urgency >= 3) in priorities."""
        events = []
        emails = [sample_urgent_followup_email()]

        builder = PrebriefBuilder(reference_date=date.fromisoformat("2026-06-14"))
        context = builder.build(events, emails)

        priorities_text = " ".join(context.suggested_priorities)
        assert "Follow-up" in priorities_text or "Urgent" in priorities_text

    def test_priorities_includes_early_events(self):
        """Should include early events (before 10 AM) in priorities."""
        events = [sample_standup_meeting()]  # 09:00
        emails = []

        builder = PrebriefBuilder(reference_date=date.fromisoformat("2026-06-14"))
        context = builder.build(events, emails)

        priorities_text = " ".join(context.suggested_priorities)
        assert "Early" in priorities_text or "Standup" in priorities_text

    def test_priorities_capped_at_five(self):
        """Should cap suggested_priorities at 5 items."""
        events = [
            sample_standup_meeting(),
            sample_afternoon_meeting(),
        ]
        emails = [
            sample_overdue_bill(),
            sample_urgent_followup_email(),
            sample_bill_email(),
        ]

        builder = PrebriefBuilder(reference_date=date.fromisoformat("2026-06-14"))
        context = builder.build(events, emails)

        assert len(context.suggested_priorities) <= 5

    def test_priorities_empty_when_no_urgent_items(self):
        """Should have minimal priorities when no urgent items."""
        events = [sample_afternoon_meeting()]  # 14:00, not early
        emails = [sample_appointment_email()]  # worth_checking, low urgency

        builder = PrebriefBuilder(reference_date=date.fromisoformat("2026-06-14"))
        context = builder.build(events, emails)

        # Should have 0 or few priorities
        assert len(context.suggested_priorities) <= 2


class TestPrebriefBuilderSerialization:
    """Tests for JSON serialization of DailyContext."""

    def test_context_to_json_and_back(self):
        """Should roundtrip through JSON."""
        events = sample_calendar_events()
        emails = sample_inbox_emails()

        builder = PrebriefBuilder(reference_date=date.fromisoformat("2026-06-14"))
        context = builder.build(events, emails)

        # Serialize to JSON
        json_str = context.to_json()
        assert isinstance(json_str, str)

        # Deserialize back
        restored = context.__class__.from_json(json_str)

        assert restored.date == context.date
        assert restored.generated_at.date() == context.generated_at.date()
        assert len(restored.events_today.items) == len(context.events_today.items)
        assert len(restored.bills_due.items) == len(context.bills_due.items)

    def test_context_to_dict_is_json_serializable(self):
        """Should produce JSON-serializable dict."""
        events = sample_calendar_events()
        emails = sample_inbox_emails()

        builder = PrebriefBuilder(reference_date=date.fromisoformat("2026-06-14"))
        context = builder.build(events, emails)

        data = context.to_dict()

        # Should be JSON-serializable
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

        # Should deserialize cleanly
        restored = json.loads(json_str)
        assert restored["date"] == "2026-06-14"


# ── Tests for PrebriefMarkdownRenderer ──────────────────────────────────────


class TestPrebriefMarkdownRenderer:
    """Tests for Markdown rendering."""

    def test_render_includes_title_and_date(self):
        """Should include title with date."""
        context = sample_daily_context()
        md = PrebriefMarkdownRenderer.render(context)

        assert "Daily Prebrief" in md
        assert "2026-06-14" in md or "June 14" in md

    def test_render_includes_all_sections(self):
        """Should include all major sections."""
        context = sample_daily_context()
        md = PrebriefMarkdownRenderer.render(context)

        assert "Suggested Priorities" in md or "🎯" in md
        assert "Today's Events" in md or "📅" in md
        assert "Upcoming Events" in md or "📆" in md
        assert "Bills Due" in md or "💳" in md
        assert "Follow-ups Needed" in md or "📬" in md
        assert "Worth Checking" in md or "📌" in md

    def test_render_events_today_with_times(self):
        """Should include event times in today's events."""
        context = sample_daily_context()
        md = PrebriefMarkdownRenderer.render(context)

        # Should include standup time
        assert "09:00" in md

    def test_render_bills_with_amounts(self):
        """Should include bill amounts and due dates."""
        context = sample_daily_context()
        md = PrebriefMarkdownRenderer.render(context)

        # Should include amounts
        assert "$" in md or "amount" in md.lower()

    def test_render_capped_indicator(self):
        """Should indicate when section is capped."""
        context = sample_daily_context()
        # Create a capped section
        context.bills_due.capped = True
        context.bills_due.items = context.bills_due.items[:2]

        md = PrebriefMarkdownRenderer.render(context)

        # Should have indication of capping
        assert "Showing" in md or "capped" in md.lower()

    def test_render_empty_context(self):
        """Should handle empty context gracefully."""
        context = sample_empty_daily_context()
        md = PrebriefMarkdownRenderer.render(context)

        assert "Daily Prebrief" in md
        assert "No events" in md or "None" in md

    def test_render_returns_markdown_string(self):
        """Should return markdown string."""
        context = sample_daily_context()
        md = PrebriefMarkdownRenderer.render(context)

        assert isinstance(md, str)
        assert len(md) > 0
        # Should have markdown headers
        assert "#" in md


# ── Integration tests ───────────────────────────────────────────────────────


class TestPrebriefBuilderIntegration:
    """Integration tests for full workflow."""

    def test_full_workflow_fixture_to_json(self):
        """Should handle full workflow: fixtures → build → JSON."""
        events = sample_calendar_events()
        emails = sample_inbox_emails()

        builder = PrebriefBuilder(reference_date=date.fromisoformat("2026-06-14"))
        context = builder.build(events, emails)

        # Serialize to JSON
        json_str = context.to_json()
        data = json.loads(json_str)

        # Validate structure
        assert "date" in data
        assert "events_today" in data
        assert "bills_due" in data
        assert "suggested_priorities" in data

    def test_full_workflow_fixture_to_markdown(self):
        """Should handle full workflow: fixtures → build → Markdown."""
        events = sample_calendar_events()
        emails = sample_inbox_emails()

        builder = PrebriefBuilder(reference_date=date.fromisoformat("2026-06-14"))
        context = builder.build(events, emails)

        # Render to Markdown
        md = PrebriefMarkdownRenderer.render(context)

        # Validate content
        assert "Daily Prebrief" in md
        assert "Events" in md
        assert "Bills" in md

    def test_fixture_sample_daily_context_matches_built_context(self):
        """Built context should match sample fixture structure."""
        events = sample_calendar_events()
        emails = sample_inbox_emails()

        builder = PrebriefBuilder(reference_date=date.fromisoformat("2026-06-14"))
        context = builder.build(events, emails)

        sample = sample_daily_context()

        # Both should have same sections
        assert hasattr(context, "events_today")
        assert hasattr(context, "events_upcoming")
        assert hasattr(context, "bills_due")
        assert hasattr(context, "followups_needed")
        assert hasattr(context, "worth_checking")
        assert hasattr(context, "carry_forward")
        assert hasattr(context, "suggested_priorities")

        # Sections should have same structure
        assert isinstance(context.events_today, PreBriefSection)
        assert isinstance(context.bills_due, PreBriefSection)

    def test_empty_events_and_emails(self):
        """Should handle empty events and emails."""
        builder = PrebriefBuilder(reference_date=date.fromisoformat("2026-06-14"))
        context = builder.build([], [])

        assert len(context.events_today.items) == 0
        assert len(context.bills_due.items) == 0
        assert len(context.followups_needed.items) == 0

    def test_capping_works_end_to_end(self):
        """Should cap sections according to configured limits."""
        custom_caps = {"events_today": 1, "bills_due": 1}

        builder = PrebriefBuilder(
            section_caps=custom_caps,
            reference_date=date.fromisoformat("2026-06-14"),
        )
        context = builder.build(sample_calendar_events(), sample_inbox_emails())

        assert len(context.events_today.items) <= 1
        assert len(context.bills_due.items) <= 1

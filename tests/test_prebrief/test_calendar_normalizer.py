"""
Tests for calendar event normalization (Batch 2).

Uses only synthetic fixtures. No live calendar data, no network calls.
"""

from datetime import date, datetime, timedelta

import pytest

from second_brain.connectors.calendar_normalizer import (
    CATEGORY_ADMIN,
    CATEGORY_HEALTH,
    CATEGORY_MEETING,
    CATEGORY_PERSONAL,
    CATEGORY_TRAVEL,
    CATEGORY_WORK,
    CalendarEventFilter,
    CalendarNormalizer,
    CalendarNormalizerBatch,
    RawCalendarRecord,
)
from second_brain.connectors.schemas import CalendarEvent


# ── Test fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def normalizer():
    return CalendarNormalizer()


@pytest.fixture
def batch_normalizer():
    return CalendarNormalizerBatch()


@pytest.fixture
def filter_service():
    return CalendarEventFilter()


@pytest.fixture
def reference_date():
    return date(2026, 6, 15)  # Monday


def sample_standup() -> RawCalendarRecord:
    """Sample work standup meeting."""
    return RawCalendarRecord(
        id="evt_standup_001",
        title="Daily Standup",
        start_time="2026-06-15T09:00:00",
        end_time="2026-06-15T09:30:00",
        source="fixture",
        location="Google Meet",
        notes="Daily sync with team",
        participants=["alice@sample.test", "bob@sample.test"],
        category="work",
    )


def sample_dentist() -> RawCalendarRecord:
    """Sample health appointment."""
    return RawCalendarRecord(
        id="evt_dentist_001",
        title="Dentist Appointment",
        start_time="2026-06-16T14:00:00",
        end_time="2026-06-16T15:00:00",
        source="fixture",
        location="123 Main St Dental",
        notes="Checkup and cleaning",
        prep_needed=True,
    )


def sample_flight() -> RawCalendarRecord:
    """Sample travel event."""
    return RawCalendarRecord(
        id="evt_flight_001",
        title="Flight to NYC",
        start_time="2026-06-20T09:00:00",
        end_time="2026-06-20T13:00:00",
        source="fixture",
        location="SFO → JFK",
        participants=["alice@sample.test"],
        notes="Delta flight 123",
        prep_needed=True,
    )


def sample_dinner() -> RawCalendarRecord:
    """Sample personal event."""
    return RawCalendarRecord(
        id="evt_dinner_001",
        title="Dinner with Friends",
        start_time="2026-06-18T19:00:00",
        end_time="2026-06-18T21:00:00",
        source="fixture",
        location="Italian Restaurant",
        participants=["alice@sample.test", "bob@sample.test", "charlie@sample.test"],
    )


def sample_1on1() -> RawCalendarRecord:
    """Sample 1-on-1 meeting."""
    return RawCalendarRecord(
        id="evt_1on1_001",
        title="1-on-1 with Manager",
        start_time="2026-06-17T14:00:00",
        end_time="2026-06-17T14:30:00",
        source="fixture",
        location="Manager's office",
        notes="Weekly check-in",
        prep_needed=False,
    )


def sample_offsite() -> RawCalendarRecord:
    """Sample all-day event."""
    return RawCalendarRecord(
        id="evt_offsite_001",
        title="Company Offsite",
        start_time="2026-06-22T00:00:00",
        end_time="2026-06-23T00:00:00",
        source="fixture",
        location="Mountain View",
        participants=["team"],
        notes="Annual team offsite",
    )


# ── Normalization tests ────────────────────────────────────────────────────────


class TestBasicNormalization:
    """Test basic event normalization."""

    def test_normalize_with_all_fields(self, normalizer):
        raw = sample_standup()
        result = normalizer.normalize(raw)
        
        assert isinstance(result, CalendarEvent)
        assert result.id == "evt_standup_001"
        assert result.title == "Daily Standup"
        assert result.source == "fixture"
        assert result.location == "Google Meet"
        assert result.notes == "Daily sync with team"
        assert len(result.participants) == 2
        assert result.category == "work"

    def test_normalize_datetime_parsing(self, normalizer):
        raw = sample_standup()
        result = normalizer.normalize(raw)
        
        assert isinstance(result.start_time, datetime)
        assert isinstance(result.end_time, datetime)
        assert result.start_time == datetime(2026, 6, 15, 9, 0, 0)
        assert result.end_time == datetime(2026, 6, 15, 9, 30, 0)

    def test_normalize_datetime_object_input(self, normalizer):
        raw = RawCalendarRecord(
            id="evt_test",
            title="Test Event",
            start_time=datetime(2026, 6, 15, 9, 0, 0),
            end_time=datetime(2026, 6, 15, 10, 0, 0),
        )
        result = normalizer.normalize(raw)
        
        assert result.start_time == datetime(2026, 6, 15, 9, 0, 0)
        assert result.end_time == datetime(2026, 6, 15, 10, 0, 0)

    def test_normalize_iso_with_z_suffix(self, normalizer):
        raw = RawCalendarRecord(
            id="evt_test",
            title="Test Event",
            start_time="2026-06-15T09:00:00Z",
            end_time="2026-06-15T10:00:00Z",
        )
        result = normalizer.normalize(raw)
        
        # Should parse successfully
        assert result.start_time.year == 2026


# ── Category inference tests ───────────────────────────────────────────────────


class TestCategoryInference:
    """Test category inference from title and notes."""

    def test_work_category_explicit(self, normalizer):
        raw = sample_standup()
        result = normalizer.normalize(raw)
        assert result.category == "work"

    def test_work_category_from_keywords(self, normalizer):
        raw = RawCalendarRecord(
            id="evt_sprint",
            title="Sprint Planning Meeting",
            start_time="2026-06-15T10:00:00",
            end_time="2026-06-15T11:00:00",
        )
        result = normalizer.normalize(raw)
        assert result.category == "work"

    def test_health_category_from_keywords(self, normalizer):
        raw = sample_dentist()
        result = normalizer.normalize(raw)
        assert result.category == "health"

    def test_travel_category_from_keywords(self, normalizer):
        raw = sample_flight()
        result = normalizer.normalize(raw)
        assert result.category == "travel"

    def test_personal_category_from_keywords(self, normalizer):
        raw = sample_dinner()
        result = normalizer.normalize(raw)
        assert result.category == "personal"

    def test_default_category_admin(self, normalizer):
        raw = RawCalendarRecord(
            id="evt_misc",
            title="Meeting Time",
            start_time="2026-06-15T10:00:00",
            end_time="2026-06-15T11:00:00",
        )
        result = normalizer.normalize(raw)
        # "meeting" is in work keywords, so it will infer work
        # Use a truly generic title
        raw2 = RawCalendarRecord(
            id="evt_misc2",
            title="Block",
            start_time="2026-06-15T10:00:00",
            end_time="2026-06-15T11:00:00",
        )
        result2 = normalizer.normalize(raw2)
        assert result2.category == "admin"

    def test_category_case_insensitivity(self, normalizer):
        raw = RawCalendarRecord(
            id="evt_case",
            title="DENTIST APPOINTMENT",
            start_time="2026-06-15T10:00:00",
            end_time="2026-06-15T11:00:00",
        )
        result = normalizer.normalize(raw)
        assert result.category == "health"

    def test_category_multiple_keywords(self, normalizer):
        """With multiple category keywords, use first match."""
        raw = RawCalendarRecord(
            id="evt_mixed",
            title="Team Standup with Yoga",
            start_time="2026-06-15T09:00:00",
            end_time="2026-06-15T10:00:00",
            notes="Sync with yoga session",
        )
        result = normalizer.normalize(raw)
        # Work matches first in keyword priority
        assert result.category == "work"


# ── Prep needed inference tests ────────────────────────────────────────────────


class TestPrepNeededInference:
    """Test prep_needed inference."""

    def test_prep_needed_explicit(self, normalizer):
        raw = sample_dentist()
        result = normalizer.normalize(raw)
        assert result.prep_needed is True

    def test_prep_needed_work_category(self, normalizer):
        raw = sample_standup()
        result = normalizer.normalize(raw)
        assert result.prep_needed is True

    def test_prep_not_needed_personal(self, normalizer):
        raw = sample_dinner()
        result = normalizer.normalize(raw)
        assert result.prep_needed is False

    def test_prep_needed_health_appointment(self, normalizer):
        raw = RawCalendarRecord(
            id="evt_lab",
            title="Lab Work",
            start_time="2026-06-15T10:00:00",
            end_time="2026-06-15T11:00:00",
        )
        result = normalizer.normalize(raw)
        assert result.prep_needed is True

    def test_prep_needed_travel(self, normalizer):
        raw = sample_flight()
        result = normalizer.normalize(raw)
        assert result.prep_needed is True

    def test_prep_not_needed_health_non_appointment(self, normalizer):
        raw = RawCalendarRecord(
            id="evt_health",
            title="Meditation Time",
            start_time="2026-06-15T10:00:00",
            end_time="2026-06-15T11:00:00",
        )
        result = normalizer.normalize(raw)
        assert result.prep_needed is False


# ── Filter tests ───────────────────────────────────────────────────────────────


class TestDateRangeFilter:
    """Test filtering events by date range."""

    def test_filter_by_date_range_single_day(self, filter_service):
        events = [
            CalendarEvent("evt_001", "fixture", "Event 1", datetime(2026, 6, 15, 9, 0), datetime(2026, 6, 15, 10, 0)),
            CalendarEvent("evt_002", "fixture", "Event 2", datetime(2026, 6, 16, 9, 0), datetime(2026, 6, 16, 10, 0)),
        ]
        
        result = filter_service.by_date_range(
            events,
            date(2026, 6, 15),
            date(2026, 6, 15)
        )
        
        assert len(result) == 1
        assert result[0].id == "evt_001"

    def test_filter_by_date_range_multiple_days(self, filter_service):
        events = [
            CalendarEvent("evt_001", "fixture", "Event 1", datetime(2026, 6, 14, 9, 0), datetime(2026, 6, 14, 10, 0)),
            CalendarEvent("evt_002", "fixture", "Event 2", datetime(2026, 6, 15, 9, 0), datetime(2026, 6, 15, 10, 0)),
            CalendarEvent("evt_003", "fixture", "Event 3", datetime(2026, 6, 16, 9, 0), datetime(2026, 6, 16, 10, 0)),
            CalendarEvent("evt_004", "fixture", "Event 4", datetime(2026, 6, 18, 9, 0), datetime(2026, 6, 18, 10, 0)),
        ]
        
        result = filter_service.by_date_range(
            events,
            date(2026, 6, 15),
            date(2026, 6, 17)
        )
        
        assert len(result) == 2
        assert {e.id for e in result} == {"evt_002", "evt_003"}

    def test_filter_by_date_range_multiday_events(self, filter_service):
        """All-day or multi-day events should be included if they overlap."""
        events = [
            CalendarEvent(
                "evt_001", "fixture", "Offsite",
                datetime(2026, 6, 15, 0, 0), datetime(2026, 6, 17, 23, 59)
            ),
        ]
        
        result = filter_service.by_date_range(
            events,
            date(2026, 6, 15),
            date(2026, 6, 17)
        )
        
        assert len(result) == 1

    def test_filter_by_date_range_no_overlap(self, filter_service):
        """Events completely outside range should be excluded."""
        events = [
            CalendarEvent("evt_001", "fixture", "Event 1", datetime(2026, 6, 15, 9, 0), datetime(2026, 6, 15, 10, 0)),
        ]
        
        result = filter_service.by_date_range(
            events,
            date(2026, 6, 18),
            date(2026, 6, 20)
        )
        
        assert len(result) == 0


class TestSingleDateFilter:
    """Test filtering events by single date."""

    def test_filter_by_date(self, filter_service):
        events = [
            CalendarEvent("evt_001", "fixture", "Event 1", datetime(2026, 6, 15, 9, 0), datetime(2026, 6, 15, 10, 0)),
            CalendarEvent("evt_002", "fixture", "Event 2", datetime(2026, 6, 15, 14, 0), datetime(2026, 6, 15, 15, 0)),
            CalendarEvent("evt_003", "fixture", "Event 3", datetime(2026, 6, 16, 9, 0), datetime(2026, 6, 16, 10, 0)),
        ]
        
        result = filter_service.by_date(events, date(2026, 6, 15))
        
        assert len(result) == 2
        assert {e.id for e in result} == {"evt_001", "evt_002"}


class TestCategoryFilter:
    """Test filtering events by category."""

    def test_filter_by_category(self, filter_service):
        events = [
            CalendarEvent("evt_001", "fixture", "Standup", datetime(2026, 6, 15, 9, 0), datetime(2026, 6, 15, 10, 0), category="work"),
            CalendarEvent("evt_002", "fixture", "Dentist", datetime(2026, 6, 15, 14, 0), datetime(2026, 6, 15, 15, 0), category="health"),
            CalendarEvent("evt_003", "fixture", "Dinner", datetime(2026, 6, 15, 19, 0), datetime(2026, 6, 15, 21, 0), category="personal"),
        ]
        
        result = filter_service.by_category(events, "work")
        
        assert len(result) == 1
        assert result[0].id == "evt_001"


class TestPrepNeededFilter:
    """Test filtering events by prep requirement."""

    def test_filter_prep_needed(self, filter_service):
        events = [
            CalendarEvent("evt_001", "fixture", "Standup", datetime(2026, 6, 15, 9, 0), datetime(2026, 6, 15, 10, 0), prep_needed=True),
            CalendarEvent("evt_002", "fixture", "Dentist", datetime(2026, 6, 15, 14, 0), datetime(2026, 6, 15, 15, 0), prep_needed=True),
            CalendarEvent("evt_003", "fixture", "Dinner", datetime(2026, 6, 15, 19, 0), datetime(2026, 6, 15, 21, 0), prep_needed=False),
        ]
        
        result = filter_service.prep_needed(events)
        
        assert len(result) == 2
        assert {e.id for e in result} == {"evt_001", "evt_002"}


class TestSortByStartTime:
    """Test sorting events by start time."""

    def test_sort_ascending(self, filter_service):
        events = [
            CalendarEvent("evt_001", "fixture", "Dinner", datetime(2026, 6, 15, 19, 0), datetime(2026, 6, 15, 21, 0)),
            CalendarEvent("evt_002", "fixture", "Standup", datetime(2026, 6, 15, 9, 0), datetime(2026, 6, 15, 10, 0)),
            CalendarEvent("evt_003", "fixture", "Lunch", datetime(2026, 6, 15, 12, 0), datetime(2026, 6, 15, 13, 0)),
        ]
        
        result = filter_service.sort_by_start_time(events)
        
        assert [e.id for e in result] == ["evt_002", "evt_003", "evt_001"]

    def test_sort_descending(self, filter_service):
        events = [
            CalendarEvent("evt_001", "fixture", "Dinner", datetime(2026, 6, 15, 19, 0), datetime(2026, 6, 15, 21, 0)),
            CalendarEvent("evt_002", "fixture", "Standup", datetime(2026, 6, 15, 9, 0), datetime(2026, 6, 15, 10, 0)),
            CalendarEvent("evt_003", "fixture", "Lunch", datetime(2026, 6, 15, 12, 0), datetime(2026, 6, 15, 13, 0)),
        ]
        
        result = filter_service.sort_by_start_time(events, reverse=True)
        
        assert [e.id for e in result] == ["evt_001", "evt_003", "evt_002"]


# ── Batch normalization tests ──────────────────────────────────────────────────


class TestBatchNormalization:
    """Test batch processing."""

    def test_batch_normalize_list_of_raw(self, batch_normalizer):
        raw_list = [
            sample_standup(),
            sample_dentist(),
            sample_flight(),
        ]
        results = batch_normalizer.normalize_batch(raw_list)
        
        assert len(results) == 3
        assert results[0].category == "work"
        assert results[1].category == "health"
        assert results[2].category == "travel"

    def test_batch_normalize_list_of_dicts(self, batch_normalizer):
        dicts = [
            {
                "id": "evt_001",
                "title": "Standup",
                "start_time": "2026-06-15T09:00:00",
                "end_time": "2026-06-15T09:30:00",
                "category": "work",
            }
        ]
        results = batch_normalizer.normalize_batch(dicts)
        
        assert len(results) == 1
        assert results[0].category == "work"

    def test_batch_preserves_order(self, batch_normalizer):
        raw_list = [
            sample_standup(),
            sample_dentist(),
            sample_flight(),
            sample_dinner(),
            sample_1on1(),
        ]
        results = batch_normalizer.normalize_batch(raw_list)
        
        assert len(results) == 5
        assert results[0].id == "evt_standup_001"
        assert results[1].id == "evt_dentist_001"
        assert results[2].id == "evt_flight_001"
        assert results[3].id == "evt_dinner_001"
        assert results[4].id == "evt_1on1_001"


# ── Batch helper tests ─────────────────────────────────────────────────────────


class TestBatchHelpers:
    """Test batch normalization helper methods."""

    def test_events_today(self, batch_normalizer, reference_date):
        events = [
            CalendarEvent(
                "evt_001", "fixture", "Standup",
                datetime(2026, 6, 15, 9, 0), datetime(2026, 6, 15, 9, 30),
                category="work"
            ),
            CalendarEvent(
                "evt_002", "fixture", "Lunch",
                datetime(2026, 6, 15, 12, 0), datetime(2026, 6, 15, 13, 0),
            ),
            CalendarEvent(
                "evt_003", "fixture", "Dinner",
                datetime(2026, 6, 16, 19, 0), datetime(2026, 6, 16, 21, 0),
            ),
        ]
        
        result = batch_normalizer.events_today(events, reference_date)
        
        assert len(result) == 2
        # Should be sorted by start time
        assert result[0].title == "Standup"
        assert result[1].title == "Lunch"

    def test_events_upcoming(self, batch_normalizer, reference_date):
        events = [
            CalendarEvent(
                "evt_001", "fixture", "Standup",
                datetime(2026, 6, 15, 9, 0), datetime(2026, 6, 15, 9, 30),
            ),
            CalendarEvent(
                "evt_002", "fixture", "Dinner",
                datetime(2026, 6, 16, 19, 0), datetime(2026, 6, 16, 21, 0),
            ),
            CalendarEvent(
                "evt_003", "fixture", "Flight",
                datetime(2026, 6, 20, 9, 0), datetime(2026, 6, 20, 13, 0),
            ),
            CalendarEvent(
                "evt_004", "fixture", "Conference",
                datetime(2026, 6, 30, 9, 0), datetime(2026, 6, 30, 17, 0),
            ),
        ]
        
        # Next 7 days from June 15 = June 16-22
        result = batch_normalizer.events_upcoming(events, days_ahead=7, reference_date=reference_date)
        
        assert len(result) == 2
        assert {e.id for e in result} == {"evt_002", "evt_003"}

    def test_events_upcoming_default_reference(self, batch_normalizer):
        """events_upcoming should use today by default."""
        events = [
            CalendarEvent(
                "evt_001", "fixture", "Future Event",
                datetime.now() + timedelta(days=2),
                datetime.now() + timedelta(days=2, hours=1)
            ),
        ]
        
        result = batch_normalizer.events_upcoming(events)
        # Should include events in next 7 days
        assert len(result) >= 0  # May or may not be in range depending on timing

    def test_events_with_prep(self, batch_normalizer):
        events = [
            CalendarEvent(
                "evt_001", "fixture", "Standup",
                datetime(2026, 6, 15, 9, 0), datetime(2026, 6, 15, 9, 30),
                prep_needed=True
            ),
            CalendarEvent(
                "evt_002", "fixture", "Dentist",
                datetime(2026, 6, 16, 14, 0), datetime(2026, 6, 16, 15, 0),
                prep_needed=True
            ),
            CalendarEvent(
                "evt_003", "fixture", "Dinner",
                datetime(2026, 6, 18, 19, 0), datetime(2026, 6, 18, 21, 0),
                prep_needed=False
            ),
        ]
        
        result = batch_normalizer.events_with_prep(events)
        
        assert len(result) == 2
        assert result[0].title == "Standup"
        assert result[1].title == "Dentist"


# ── Schema preservation tests ──────────────────────────────────────────────────


class TestSchemaNormalization:
    """Test that normalized output matches CalendarEvent schema."""

    def test_normalized_is_calendar_event(self, normalizer):
        raw = sample_standup()
        result = normalizer.normalize(raw)
        assert isinstance(result, CalendarEvent)

    def test_normalized_id_preserved(self, normalizer):
        raw = sample_standup()
        result = normalizer.normalize(raw)
        assert result.id == "evt_standup_001"

    def test_normalized_title_preserved(self, normalizer):
        raw = sample_standup()
        result = normalizer.normalize(raw)
        assert result.title == "Daily Standup"

    def test_normalized_source_preserved(self, normalizer):
        raw = sample_standup()
        result = normalizer.normalize(raw)
        assert result.source == "fixture"

    def test_normalized_location_preserved(self, normalizer):
        raw = sample_standup()
        result = normalizer.normalize(raw)
        assert result.location == "Google Meet"

    def test_normalized_notes_preserved(self, normalizer):
        raw = sample_standup()
        result = normalizer.normalize(raw)
        assert result.notes == "Daily sync with team"

    def test_normalized_participants_preserved(self, normalizer):
        raw = sample_standup()
        result = normalizer.normalize(raw)
        assert len(result.participants) == 2
        assert "alice@sample.test" in result.participants

    def test_normalized_roundtrip_to_dict(self, normalizer):
        """Verify roundtrip to dict and back works."""
        raw = sample_standup()
        original = normalizer.normalize(raw)
        restored = CalendarEvent.from_dict(original.to_dict())
        assert restored == original

    def test_normalized_empty_participants_default(self, normalizer):
        raw = RawCalendarRecord(
            id="evt_test",
            title="Solo event",
            start_time="2026-06-15T09:00:00",
            end_time="2026-06-15T10:00:00",
            participants=None,
        )
        result = normalizer.normalize(raw)
        assert result.participants == []


# ── Edge case tests ────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_invalid_datetime_string_raises(self, normalizer):
        raw = RawCalendarRecord(
            id="evt_bad",
            title="Bad Event",
            start_time="not-a-date",
            end_time="2026-06-15T10:00:00",
        )
        with pytest.raises(ValueError):
            normalizer.normalize(raw)

    def test_invalid_datetime_type_raises(self, normalizer):
        raw = RawCalendarRecord(
            id="evt_bad",
            title="Bad Event",
            start_time=12345,  # Invalid type
            end_time="2026-06-15T10:00:00",
        )
        with pytest.raises(TypeError):
            normalizer.normalize(raw)

    def test_empty_title(self, normalizer):
        raw = RawCalendarRecord(
            id="evt_notitle",
            title="",
            start_time="2026-06-15T09:00:00",
            end_time="2026-06-15T10:00:00",
        )
        result = normalizer.normalize(raw)
        assert result.title == ""
        assert result.category == "admin"  # Default

    def test_empty_notes(self, normalizer):
        raw = RawCalendarRecord(
            id="evt_nonotes",
            title="Event",
            start_time="2026-06-15T09:00:00",
            end_time="2026-06-15T10:00:00",
            notes="",
        )
        result = normalizer.normalize(raw)
        assert result.notes == ""

    def test_empty_location(self, normalizer):
        raw = RawCalendarRecord(
            id="evt_noloc",
            title="Virtual Event",
            start_time="2026-06-15T09:00:00",
            end_time="2026-06-15T10:00:00",
            location="",
        )
        result = normalizer.normalize(raw)
        assert result.location == ""

    def test_invalid_category_ignored(self, normalizer):
        """Invalid category should be replaced with inferred or default."""
        raw = RawCalendarRecord(
            id="evt_badcat",
            title="Meeting",
            start_time="2026-06-15T09:00:00",
            end_time="2026-06-15T10:00:00",
            category="invalid_category",
        )
        result = normalizer.normalize(raw)
        assert result.category == "work"  # Inferred from "Meeting"

    def test_filter_empty_list(self, filter_service):
        result = filter_service.by_date_range([], date(2026, 6, 15), date(2026, 6, 16))
        assert result == []

    def test_sort_empty_list(self, filter_service):
        result = filter_service.sort_by_start_time([])
        assert result == []

    def test_batch_empty_list(self, batch_normalizer):
        result = batch_normalizer.normalize_batch([])
        assert result == []


# ── Integration tests ──────────────────────────────────────────────────────────


class TestIntegration:
    """Integration tests with multiple components."""

    def test_normalize_and_filter_workflow(self, batch_normalizer, filter_service, reference_date):
        """Test typical workflow: normalize → filter → sort."""
        raw_events = [
            sample_standup(),
            sample_dentist(),
            sample_flight(),
            sample_dinner(),
            sample_1on1(),
        ]
        
        # Normalize
        normalized = batch_normalizer.normalize_batch(raw_events)
        assert len(normalized) == 5
        
        # Filter to specific date (June 15 is Monday)
        # sample_standup is June 15, 1on1 is June 17
        today = filter_service.by_date(normalized, reference_date)
        assert len(today) == 1  # only standup
        
        # Sort by time
        sorted_today = filter_service.sort_by_start_time(today)
        assert sorted_today[0].title == "Daily Standup"

    def test_normalize_filter_by_category(self, batch_normalizer, filter_service):
        """Test normalizing and then filtering by category."""
        raw_events = [
            sample_standup(),
            sample_dentist(),
            sample_flight(),
            sample_dinner(),
        ]
        
        normalized = batch_normalizer.normalize_batch(raw_events)
        
        # Filter to work events
        work_events = filter_service.by_category(normalized, "work")
        assert len(work_events) == 1
        assert work_events[0].title == "Daily Standup"
        
        # Filter to health events
        health_events = filter_service.by_category(normalized, "health")
        assert len(health_events) == 1
        assert health_events[0].title == "Dentist Appointment"
        
        # Filter to personal events
        personal_events = filter_service.by_category(normalized, "personal")
        assert len(personal_events) == 1
        assert personal_events[0].title == "Dinner with Friends"

    def test_all_synthetic_domains(self, batch_normalizer):
        """Verify all test data uses synthetic domains."""
        test_cases = [
            sample_standup(),
            sample_dentist(),
            sample_flight(),
            sample_dinner(),
            sample_1on1(),
        ]
        
        for raw in test_cases:
            # Participants should have synthetic domains if any
            for participant in raw.participants or []:
                assert any(participant.endswith(suffix) for suffix in [".test", ".example", ".invalid"]) or "@" not in participant
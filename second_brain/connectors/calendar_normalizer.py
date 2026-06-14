"""
Calendar event normalization for Prebrief Batch 2.

Converts synthetic/raw calendar-like records into normalized CalendarEvent schema.
Provides filtering, date-range operations, and dry-run fixture mode.

Policy:
- Offline, deterministic processing of synthetic fixtures only.
- No live OAuth flow, no network calls.
- Dry-run mode supports testing without live calendar sources.
- No real calendar data, no PII in source or results.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, time
from typing import Any, Optional

from .schemas import CalendarEvent


# ── Category definitions ───────────────────────────────────────────────────────

CATEGORY_ADMIN = "admin"
CATEGORY_WORK = "work"
CATEGORY_PERSONAL = "personal"
CATEGORY_HEALTH = "health"
CATEGORY_TRAVEL = "travel"
CATEGORY_MEETING = "meeting"

VALID_CATEGORIES = {
    CATEGORY_ADMIN,
    CATEGORY_WORK,
    CATEGORY_PERSONAL,
    CATEGORY_HEALTH,
    CATEGORY_TRAVEL,
    CATEGORY_MEETING,
}

DEFAULT_CATEGORY = CATEGORY_ADMIN


@dataclass
class RawCalendarRecord:
    """Raw calendar-like record from any source (fixture, API, etc.)."""

    id: str
    title: str
    start_time: str | datetime
    end_time: str | datetime
    source: str = "fixture"
    participants: list[str] | None = None
    location: str = ""
    notes: str = ""
    category: str = ""
    prep_needed: bool = False


class CalendarNormalizer:
    """Normalize raw calendar records to CalendarEvent schema."""

    def __init__(self):
        """Initialize patterns for extraction."""
        # Keywords for category inference
        self._work_keywords = {
            "standup", "meeting", "sync", "sprint", "review", "planning",
            "retrospective", "retro", "demo", "presentation", "conference",
            "workshop", "training", "onboarding", "interview", "candidate",
            "one-on-one", "1-1", "1on1", "team", "project", "kickoff",
            "deadline", "deployment", "release", "product", "engineering",
        }

        self._health_keywords = {
            "doctor", "dentist", "appointment", "checkup", "check-up",
            "therapy", "counseling", "meditation", "yoga", "gym", "exercise",
            "run", "walk", "sport", "physical", "mental", "wellness",
            "vaccination", "vaccine", "lab", "test", "medical",
        }

        self._travel_keywords = {
            "flight", "travel", "trip", "airport", "train", "hotel",
            "vacation", "conference", "conference", "commute", "drive",
            "roadtrip", "road trip", "getaway", "destination",
        }

        self._personal_keywords = {
            "personal", "family", "friend", "birthday", "anniversary",
            "dinner", "lunch", "coffee", "date", "wedding", "celebration",
            "event", "party", "gathering", "social",
        }

    def normalize(self, raw: RawCalendarRecord) -> CalendarEvent:
        """
        Normalize a raw calendar record to CalendarEvent schema.

        Args:
            raw: RawCalendarRecord to normalize

        Returns:
            Normalized CalendarEvent object
        """
        # Parse timestamps
        start_time = self._parse_datetime(raw.start_time)
        end_time = self._parse_datetime(raw.end_time)

        # Infer category if not provided
        category = self._infer_category(raw.title, raw.notes, raw.category)

        # Infer prep_needed if not explicitly set
        prep_needed = raw.prep_needed or self._infer_prep_needed(category, raw.title)

        return CalendarEvent(
            id=raw.id,
            source=raw.source,
            title=raw.title,
            start_time=start_time,
            end_time=end_time,
            participants=raw.participants or [],
            location=raw.location,
            notes=raw.notes,
            category=category,
            prep_needed=prep_needed,
        )

    def _parse_datetime(self, dt: str | datetime) -> datetime:
        """
        Parse datetime from string or datetime object.

        Args:
            dt: ISO string or datetime object

        Returns:
            datetime object
        """
        if isinstance(dt, str):
            try:
                # Handle ISO format with or without 'Z' suffix
                dt_str = dt.replace("Z", "+00:00")
                return datetime.fromisoformat(dt_str)
            except (ValueError, TypeError):
                raise ValueError(f"Invalid datetime string: {dt}")
        elif isinstance(dt, datetime):
            return dt
        else:
            raise TypeError(f"Expected str or datetime, got {type(dt)}")

    def _infer_category(self, title: str, notes: str, provided_category: str) -> str:
        """
        Infer category from title/notes if not provided.

        Priority:
        1. Use provided category if valid
        2. Infer from keywords in title/notes
        3. Default to admin

        Args:
            title: Event title
            notes: Event notes
            provided_category: Explicitly provided category

        Returns:
            Valid category string
        """
        if provided_category and provided_category in VALID_CATEGORIES:
            return provided_category

        combined = (title + " " + notes).lower()

        # Check work
        work_score = sum(1 for kw in self._work_keywords if kw in combined)
        if work_score >= 1:
            return CATEGORY_WORK

        # Check health
        health_score = sum(1 for kw in self._health_keywords if kw in combined)
        if health_score >= 1:
            return CATEGORY_HEALTH

        # Check travel
        travel_score = sum(1 for kw in self._travel_keywords if kw in combined)
        if travel_score >= 1:
            return CATEGORY_TRAVEL

        # Check personal
        personal_score = sum(1 for kw in self._personal_keywords if kw in combined)
        if personal_score >= 1:
            return CATEGORY_PERSONAL

        return DEFAULT_CATEGORY

    def _infer_prep_needed(self, category: str, title: str) -> bool:
        """
        Infer whether prep is needed based on category and title.

        Args:
            category: Event category
            title: Event title

        Returns:
            Boolean indicating if prep is needed
        """
        # Meetings typically need prep
        if category == CATEGORY_WORK:
            return True

        # Health appointments might need prep
        if category == CATEGORY_HEALTH:
            prep_keywords = {"appointment", "checkup", "check-up", "vaccination", "lab"}
            if any(kw in title.lower() for kw in prep_keywords):
                return True

        # Travel events might need prep
        if category == CATEGORY_TRAVEL:
            prep_keywords = {"flight", "trip", "travel"}
            if any(kw in title.lower() for kw in prep_keywords):
                return True

        return False


class CalendarEventFilter:
    """Filter and query calendar events by date range and attributes."""

    @staticmethod
    def by_date_range(
        events: list[CalendarEvent],
        start_date: date,
        end_date: date,
    ) -> list[CalendarEvent]:
        """
        Filter events that fall within a date range.

        An event overlaps the range if:
        - event.start_time.date() <= end_date AND
        - event.end_time.date() >= start_date

        Args:
            events: List of CalendarEvent objects
            start_date: Inclusive start date
            end_date: Inclusive end date

        Returns:
            Filtered list of events
        """
        result = []
        for event in events:
            event_start_date = event.start_time.date()
            event_end_date = event.end_time.date()

            # Check if event overlaps the range
            if event_start_date <= end_date and event_end_date >= start_date:
                result.append(event)

        return result

    @staticmethod
    def by_category(
        events: list[CalendarEvent],
        category: str,
    ) -> list[CalendarEvent]:
        """
        Filter events by category.

        Args:
            events: List of CalendarEvent objects
            category: Category to filter by

        Returns:
            Filtered list of events
        """
        return [e for e in events if e.category == category]

    @staticmethod
    def by_date(
        events: list[CalendarEvent],
        target_date: date,
    ) -> list[CalendarEvent]:
        """
        Filter events that occur on a specific date.

        An event occurs on a date if its date range includes that date.

        Args:
            events: List of CalendarEvent objects
            target_date: Date to filter by

        Returns:
            Filtered list of events
        """
        return CalendarEventFilter.by_date_range(events, target_date, target_date)

    @staticmethod
    def prep_needed(
        events: list[CalendarEvent],
    ) -> list[CalendarEvent]:
        """
        Filter events that require preparation.

        Args:
            events: List of CalendarEvent objects

        Returns:
            Filtered list of events with prep_needed=True
        """
        return [e for e in events if e.prep_needed]

    @staticmethod
    def sort_by_start_time(
        events: list[CalendarEvent],
        reverse: bool = False,
    ) -> list[CalendarEvent]:
        """
        Sort events by start_time.

        Args:
            events: List of CalendarEvent objects
            reverse: If True, sort descending

        Returns:
            Sorted list of events
        """
        return sorted(events, key=lambda e: e.start_time, reverse=reverse)


class CalendarNormalizerBatch:
    """Process multiple raw calendar records in batch."""

    def __init__(self):
        self.normalizer = CalendarNormalizer()
        self.filter = CalendarEventFilter()

    def normalize_batch(
        self,
        raw_records: list[RawCalendarRecord] | list[dict[str, Any]],
    ) -> list[CalendarEvent]:
        """
        Normalize a batch of raw calendar records.

        Args:
            raw_records: List of RawCalendarRecord or dicts

        Returns:
            List of normalized CalendarEvent objects
        """
        results = []
        for record in raw_records:
            # Convert dict to RawCalendarRecord if needed
            if isinstance(record, dict):
                raw = RawCalendarRecord(
                    id=record["id"],
                    title=record["title"],
                    start_time=record["start_time"],
                    end_time=record["end_time"],
                    source=record.get("source", "fixture"),
                    participants=record.get("participants"),
                    location=record.get("location", ""),
                    notes=record.get("notes", ""),
                    category=record.get("category", ""),
                    prep_needed=record.get("prep_needed", False),
                )
            else:
                raw = record

            normalized = self.normalizer.normalize(raw)
            results.append(normalized)

        return results

    def events_today(
        self,
        events: list[CalendarEvent],
        reference_date: date | None = None,
    ) -> list[CalendarEvent]:
        """
        Filter events for today.

        Args:
            events: List of CalendarEvent objects
            reference_date: Date to use as 'today' (defaults to today)

        Returns:
            Filtered and sorted list of events
        """
        if reference_date is None:
            reference_date = date.today()

        filtered = self.filter.by_date(events, reference_date)
        return self.filter.sort_by_start_time(filtered)

    def events_upcoming(
        self,
        events: list[CalendarEvent],
        days_ahead: int = 7,
        reference_date: date | None = None,
    ) -> list[CalendarEvent]:
        """
        Filter upcoming events for next N days (excluding today).

        Args:
            events: List of CalendarEvent objects
            days_ahead: Number of days to look ahead (default 7)
            reference_date: Date to use as reference (defaults to today)

        Returns:
            Filtered and sorted list of events
        """
        if reference_date is None:
            reference_date = date.today()

        start_date = reference_date + timedelta(days=1)
        end_date = reference_date + timedelta(days=days_ahead)

        filtered = self.filter.by_date_range(events, start_date, end_date)
        return self.filter.sort_by_start_time(filtered)

    def events_with_prep(
        self,
        events: list[CalendarEvent],
    ) -> list[CalendarEvent]:
        """
        Filter events that need preparation.

        Args:
            events: List of CalendarEvent objects

        Returns:
            Filtered and sorted list of events
        """
        filtered = self.filter.prep_needed(events)
        return self.filter.sort_by_start_time(filtered)

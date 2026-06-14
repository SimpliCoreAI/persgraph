"""
Prebrief Builder for Batch 6.

Combines normalized CalendarEvent and InboxEmail inputs into DailyContext output.
Provides ranking, capping, and both machine-readable (JSON) and human-readable (Markdown) rendering.

Policy:
- Offline, deterministic processing of normalized inputs only.
- No live network calls, no real user data.
- Fixture-based testing with synthetic data only.
- Output shaped for data/prebrief_context.json and Markdown rendering.

Architecture:
- PrebriefBuilder: Core class combining events and emails into DailyContext
- PrebriefContextRanker: Ranking/capping logic for each section
- PrebriefMarkdownRenderer: Human-readable Markdown output
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from .schemas import CalendarEvent, InboxEmail, DailyContext, PreBriefSection


# ── Ranking and capping defaults ───────────────────────────────────────────────

DEFAULT_SECTION_CAPS = {
    "events_today": 10,
    "events_upcoming": 5,
    "bills_due": 5,
    "followups_needed": 5,
    "worth_checking": 5,
    "carry_forward": 3,
}


@dataclass
class SectionConfig:
    """Configuration for ranking a single prebrief section."""

    name: str
    cap_limit: int = 0
    priority_order: list[str] = None  # Field names for sort order

    def __post_init__(self):
        if self.priority_order is None:
            self.priority_order = []


class PrebriefContextRanker:
    """
    Ranking and capping logic for prebrief sections.

    Handles:
    - Ranking items within each section (by date, urgency, etc.)
    - Capping section size with cap_limit
    - Flagging when items were capped
    """

    @staticmethod
    def rank_and_cap_events_today(
        events: list[CalendarEvent],
        cap_limit: int = DEFAULT_SECTION_CAPS["events_today"],
    ) -> PreBriefSection:
        """
        Rank and cap events for today.

        Ranking: by start_time (ascending)
        """
        sorted_events = sorted(events, key=lambda e: e.start_time)
        capped = len(sorted_events) > cap_limit if cap_limit > 0 else False
        items = [
            {
                "id": e.id,
                "title": e.title,
                "start_time": e.start_time.isoformat(),
                "end_time": e.end_time.isoformat(),
                "location": e.location,
                "category": e.category,
            }
            for e in sorted_events[: cap_limit if cap_limit > 0 else None]
        ]
        return PreBriefSection(items=items, capped=capped, cap_limit=cap_limit)

    @staticmethod
    def rank_and_cap_events_upcoming(
        events: list[CalendarEvent],
        cap_limit: int = DEFAULT_SECTION_CAPS["events_upcoming"],
    ) -> PreBriefSection:
        """
        Rank and cap upcoming events (next 7 days, excluding today).

        Ranking: by start_time (ascending)
        """
        sorted_events = sorted(events, key=lambda e: e.start_time)
        capped = len(sorted_events) > cap_limit if cap_limit > 0 else False
        items = [
            {
                "id": e.id,
                "title": e.title,
                "start_time": e.start_time.isoformat(),
                "end_time": e.end_time.isoformat(),
                "location": e.location,
                "category": e.category,
            }
            for e in sorted_events[: cap_limit if cap_limit > 0 else None]
        ]
        return PreBriefSection(items=items, capped=capped, cap_limit=cap_limit)

    @staticmethod
    def rank_and_cap_bills_due(
        emails: list[InboxEmail],
        cap_limit: int = DEFAULT_SECTION_CAPS["bills_due"],
    ) -> PreBriefSection:
        """
        Rank and cap bills due.

        Ranking: by due_date (ascending, None last), then urgency (descending)
        """
        # Filter to bill bucket
        bills = [e for e in emails if e.bucket == "bill"]

        # Sort: due_date ascending (None last), then urgency descending
        def sort_key(e: InboxEmail):
            due_key = (
                e.due_date if e.due_date else date.max
            )  # None → treat as far future
            return (due_key, -e.urgency)

        sorted_bills = sorted(bills, key=sort_key)
        capped = len(sorted_bills) > cap_limit if cap_limit > 0 else False
        items = [
            {
                "id": e.id,
                "subject": e.subject,
                "sender": e.sender,
                "due_date": e.due_date.isoformat() if e.due_date else None,
                "amount": e.amount,
                "urgency": e.urgency,
            }
            for e in sorted_bills[: cap_limit if cap_limit > 0 else None]
        ]
        return PreBriefSection(items=items, capped=capped, cap_limit=cap_limit)

    @staticmethod
    def rank_and_cap_followups_needed(
        emails: list[InboxEmail],
        cap_limit: int = DEFAULT_SECTION_CAPS["followups_needed"],
    ) -> PreBriefSection:
        """
        Rank and cap follow-ups needed.

        Ranking: by urgency (descending), then timestamp (ascending)
        """
        # Filter to followup bucket
        followups = [e for e in emails if e.bucket == "followup"]

        # Sort: urgency descending, timestamp ascending
        sorted_followups = sorted(
            followups, key=lambda e: (-e.urgency, e.timestamp)
        )
        capped = len(sorted_followups) > cap_limit if cap_limit > 0 else False
        items = [
            {
                "id": e.id,
                "subject": e.subject,
                "sender": e.sender,
                "timestamp": e.timestamp.isoformat(),
                "urgency": e.urgency,
                "action_required": e.action_required,
            }
            for e in sorted_followups[: cap_limit if cap_limit > 0 else None]
        ]
        return PreBriefSection(items=items, capped=capped, cap_limit=cap_limit)

    @staticmethod
    def rank_and_cap_worth_checking(
        emails: list[InboxEmail],
        cap_limit: int = DEFAULT_SECTION_CAPS["worth_checking"],
    ) -> PreBriefSection:
        """
        Rank and cap worth-checking items.

        Ranking: by urgency (descending), then confidence (descending), then timestamp (ascending)
        """
        # Filter to worth_checking bucket
        worth_checking = [e for e in emails if e.bucket == "worth_checking"]

        # Sort: urgency descending, confidence descending, timestamp ascending
        sorted_items = sorted(
            worth_checking,
            key=lambda e: (-e.urgency, -e.confidence, e.timestamp),
        )
        capped = len(sorted_items) > cap_limit if cap_limit > 0 else False
        items = [
            {
                "id": e.id,
                "subject": e.subject,
                "sender": e.sender,
                "timestamp": e.timestamp.isoformat(),
                "urgency": e.urgency,
                "confidence": e.confidence,
            }
            for e in sorted_items[: cap_limit if cap_limit > 0 else None]
        ]
        return PreBriefSection(items=items, capped=capped, cap_limit=cap_limit)

    @staticmethod
    def rank_and_cap_carry_forward(
        emails: list[InboxEmail],
        cap_limit: int = DEFAULT_SECTION_CAPS["carry_forward"],
    ) -> PreBriefSection:
        """
        Rank and cap carry-forward (old) items.

        Ranking: by timestamp (oldest first, ascending)
        """
        # Filter to fyi bucket (lowest urgency/action)
        fyi = [e for e in emails if e.bucket == "fyi"]

        # Sort: timestamp ascending (oldest first)
        sorted_items = sorted(fyi, key=lambda e: e.timestamp)
        capped = len(sorted_items) > cap_limit if cap_limit > 0 else False
        items = [
            {
                "id": e.id,
                "subject": e.subject,
                "sender": e.sender,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in sorted_items[: cap_limit if cap_limit > 0 else None]
        ]
        return PreBriefSection(items=items, capped=capped, cap_limit=cap_limit)


class PrebriefBuilder:
    """
    Combines normalized CalendarEvent and InboxEmail into DailyContext.

    Handles:
    - Separating events into today/upcoming
    - Classifying emails into sections
    - Generating suggested priorities
    - Building complete DailyContext
    """

    def __init__(
        self,
        section_caps: dict[str, int] | None = None,
        reference_date: date | None = None,
    ):
        """
        Initialize the builder.

        Args:
            section_caps: Override default section cap limits
            reference_date: Date to use for "today" (defaults to current date)
        """
        self.section_caps = {**DEFAULT_SECTION_CAPS}
        if section_caps:
            self.section_caps.update(section_caps)
        self.reference_date = reference_date or date.today()

    def build(
        self,
        events: list[CalendarEvent],
        emails: list[InboxEmail],
    ) -> DailyContext:
        """
        Build complete DailyContext from normalized inputs.

        Args:
            events: List of normalized CalendarEvent objects
            emails: List of normalized InboxEmail objects

        Returns:
            DailyContext with all sections populated and ranked
        """
        # Separate events by date
        events_today = [
            e
            for e in events
            if e.start_time.date() == self.reference_date
        ]
        events_upcoming = [
            e
            for e in events
            if e.start_time.date()
            > self.reference_date
            and e.start_time.date()
            <= (self.reference_date + timedelta(days=7))
        ]

        # Build sections
        events_today_section = PrebriefContextRanker.rank_and_cap_events_today(
            events_today, self.section_caps["events_today"]
        )
        events_upcoming_section = PrebriefContextRanker.rank_and_cap_events_upcoming(
            events_upcoming, self.section_caps["events_upcoming"]
        )
        bills_due_section = PrebriefContextRanker.rank_and_cap_bills_due(
            emails, self.section_caps["bills_due"]
        )
        followups_needed_section = PrebriefContextRanker.rank_and_cap_followups_needed(
            emails, self.section_caps["followups_needed"]
        )
        worth_checking_section = PrebriefContextRanker.rank_and_cap_worth_checking(
            emails, self.section_caps["worth_checking"]
        )
        carry_forward_section = PrebriefContextRanker.rank_and_cap_carry_forward(
            emails, self.section_caps["carry_forward"]
        )

        # Generate suggested priorities
        suggested_priorities = self._generate_suggested_priorities(
            events_today_section,
            bills_due_section,
            followups_needed_section,
        )

        # Build DailyContext
        context = DailyContext(
            date=self.reference_date,
            generated_at=datetime.now(timezone.utc),
            events_today=events_today_section,
            events_upcoming=events_upcoming_section,
            bills_due=bills_due_section,
            followups_needed=followups_needed_section,
            worth_checking=worth_checking_section,
            carry_forward=carry_forward_section,
            suggested_priorities=suggested_priorities,
        )
        return context

    def _generate_suggested_priorities(
        self,
        events_today: PreBriefSection,
        bills_due: PreBriefSection,
        followups: PreBriefSection,
    ) -> list[str]:
        """
        Generate a short list of top priorities for the day.

        Logic:
        - Urgent bills (urgency >= 4)
        - Urgent followups (urgency >= 3)
        - Early events (before 10 AM)
        """
        priorities = []

        # Check for urgent bills
        for item in bills_due.items:
            if item.get("urgency", 0) >= 4:
                priorities.append(f"Urgent: {item.get('subject', 'Bill payment')}")

        # Check for urgent followups
        for item in followups.items:
            if item.get("urgency", 0) >= 3:
                priorities.append(
                    f"Follow-up: {item.get('subject', 'Pending action')}"
                )

        # Check for early events (before 10 AM)
        for item in events_today.items:
            start_time_str = item.get("start_time", "")
            if start_time_str:
                try:
                    dt = datetime.fromisoformat(start_time_str)
                    if dt.hour < 10:
                        priorities.append(
                            f"Early: {item.get('title', 'Event')} at {dt.strftime('%H:%M')}"
                        )
                except (ValueError, AttributeError):
                    pass

        return priorities[:5]  # Cap at 5 priorities


class PrebriefMarkdownRenderer:
    """
    Renders DailyContext as human-readable Markdown.

    Output format:
    - Title with date
    - Sections for each category
    - Simple bullet lists with relevant details
    """

    @staticmethod
    def render(context: DailyContext) -> str:
        """
        Render DailyContext as Markdown.

        Args:
            context: DailyContext to render

        Returns:
            Markdown string
        """
        lines = []

        # Title
        lines.append(f"# Daily Prebrief — {context.date.strftime('%A, %B %d, %Y')}")
        lines.append(f"*Generated: {context.generated_at.strftime('%H:%M %Z')}*")
        lines.append("")

        # Suggested Priorities
        if context.suggested_priorities:
            lines.append("## 🎯 Suggested Priorities")
            for priority in context.suggested_priorities:
                lines.append(f"- {priority}")
            lines.append("")

        # Events Today
        if context.events_today.items:
            lines.append("## 📅 Today's Events")
            if context.events_today.capped:
                lines.append(
                    f"*Showing {len(context.events_today.items)}/{len(context.events_today.items) + 1}+ events*"
                )
            for item in context.events_today.items:
                start_time_str = item.get("start_time", "")
                title = item.get("title", "Event")
                location = item.get("location", "")
                if start_time_str:
                    try:
                        dt = datetime.fromisoformat(start_time_str)
                        time_str = dt.strftime("%H:%M")
                        location_str = f" @ {location}" if location else ""
                        lines.append(f"- **{time_str}** {title}{location_str}")
                    except (ValueError, AttributeError):
                        lines.append(f"- {title}")
                else:
                    lines.append(f"- {title}")
            lines.append("")
        else:
            lines.append("## 📅 Today's Events\nNo events scheduled.")
            lines.append("")

        # Events Upcoming
        if context.events_upcoming.items:
            lines.append("## 📆 Upcoming Events (Next 7 Days)")
            if context.events_upcoming.capped:
                lines.append(
                    f"*Showing {len(context.events_upcoming.items)}/{len(context.events_upcoming.items) + 1}+ events*"
                )
            for item in context.events_upcoming.items:
                start_time_str = item.get("start_time", "")
                title = item.get("title", "Event")
                if start_time_str:
                    try:
                        dt = datetime.fromisoformat(start_time_str)
                        date_str = dt.strftime("%a, %b %d")
                        time_str = dt.strftime("%H:%M")
                        lines.append(f"- **{date_str}** @ {time_str} — {title}")
                    except (ValueError, AttributeError):
                        lines.append(f"- {title}")
                else:
                    lines.append(f"- {title}")
            lines.append("")
        else:
            lines.append("## 📆 Upcoming Events (Next 7 Days)\nNone.")
            lines.append("")

        # Bills Due
        if context.bills_due.items:
            lines.append("## 💳 Bills Due")
            if context.bills_due.capped:
                lines.append(
                    f"*Showing {len(context.bills_due.items)}/{len(context.bills_due.items) + 1}+ bills*"
                )
            for item in context.bills_due.items:
                subject = item.get("subject", "Payment")
                due_date = item.get("due_date", "")
                amount = item.get("amount")
                urgency = item.get("urgency", 0)
                urgency_str = "🔴" if urgency >= 4 else "🟡" if urgency >= 2 else "⚪"
                amount_str = f" — ${amount:.2f}" if amount else ""
                date_str = f" (Due: {due_date})" if due_date else ""
                lines.append(f"- {urgency_str} {subject}{amount_str}{date_str}")
            lines.append("")
        else:
            lines.append("## 💳 Bills Due\nNone.")
            lines.append("")

        # Follow-ups Needed
        if context.followups_needed.items:
            lines.append("## 📬 Follow-ups Needed")
            if context.followups_needed.capped:
                lines.append(
                    f"*Showing {len(context.followups_needed.items)}/{len(context.followups_needed.items) + 1}+ follow-ups*"
                )
            for item in context.followups_needed.items:
                subject = item.get("subject", "Follow-up")
                sender = item.get("sender", "")
                urgency = item.get("urgency", 0)
                urgency_str = "🔴" if urgency >= 3 else "🟡" if urgency >= 1 else "⚪"
                sender_str = f" from {sender}" if sender else ""
                lines.append(f"- {urgency_str} {subject}{sender_str}")
            lines.append("")
        else:
            lines.append("## 📬 Follow-ups Needed\nNone.")
            lines.append("")

        # Worth Checking
        if context.worth_checking.items:
            lines.append("## 📌 Worth Checking")
            if context.worth_checking.capped:
                lines.append(
                    f"*Showing {len(context.worth_checking.items)}/{len(context.worth_checking.items) + 1}+ items*"
                )
            for item in context.worth_checking.items:
                subject = item.get("subject", "Item")
                sender = item.get("sender", "")
                sender_str = f" from {sender}" if sender else ""
                lines.append(f"- {subject}{sender_str}")
            lines.append("")
        else:
            lines.append("## 📌 Worth Checking\nNone.")
            lines.append("")

        # Carry Forward
        if context.carry_forward.items:
            lines.append("## 📚 Carry Forward (Older Items)")
            if context.carry_forward.capped:
                lines.append(
                    f"*Showing {len(context.carry_forward.items)}/{len(context.carry_forward.items) + 1}+ items*"
                )
            for item in context.carry_forward.items:
                subject = item.get("subject", "Item")
                lines.append(f"- {subject}")
            lines.append("")

        return "\n".join(lines)

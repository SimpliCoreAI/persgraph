from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass
class CalendarEvent:
    id: str
    source: str
    title: str
    start_time: datetime
    end_time: datetime
    participants: list[str] = field(default_factory=list)
    location: str = ""
    notes: str = ""
    category: str = "admin"
    prep_needed: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["start_time"] = self.start_time.isoformat()
        data["end_time"] = self.end_time.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CalendarEvent":
        return cls(
            id=data["id"],
            source=data["source"],
            title=data["title"],
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]),
            participants=list(data.get("participants", [])),
            location=data.get("location", ""),
            notes=data.get("notes", ""),
            category=data.get("category", "admin"),
            prep_needed=bool(data.get("prep_needed", False)),
        )


@dataclass
class InboxEmail:
    id: str
    source: str
    sender: str
    subject: str
    timestamp: datetime
    snippet: str
    labels: list[str] = field(default_factory=list)
    bucket: str = "unclassified"
    due_date: date | None = None
    amount: float | None = None
    urgency: int = 0
    confidence: float = 0.0
    action_required: bool = False
    thread_key: str = ""
    source_ref: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["due_date"] = self.due_date.isoformat() if self.due_date else None
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InboxEmail":
        due_date = data.get("due_date")
        return cls(
            id=data["id"],
            source=data["source"],
            sender=data["sender"],
            subject=data["subject"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            snippet=data["snippet"],
            labels=list(data.get("labels", [])),
            bucket=data.get("bucket", "unclassified"),
            due_date=date.fromisoformat(due_date) if due_date else None,
            amount=data.get("amount"),
            urgency=int(data.get("urgency", 0)),
            confidence=float(data.get("confidence", 0.0)),
            action_required=bool(data.get("action_required", False)),
            thread_key=data.get("thread_key", ""),
            source_ref=data.get("source_ref", ""),
        )


@dataclass
class PreBriefSection:
    items: list[dict[str, Any]] = field(default_factory=list)
    capped: bool = False
    cap_limit: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PreBriefSection":
        return cls(
            items=list(data.get("items", [])),
            capped=bool(data.get("capped", False)),
            cap_limit=int(data.get("cap_limit", 0)),
        )


@dataclass
class DailyContext:
    date: date
    generated_at: datetime
    events_today: PreBriefSection
    events_upcoming: PreBriefSection
    bills_due: PreBriefSection
    followups_needed: PreBriefSection
    worth_checking: PreBriefSection
    carry_forward: PreBriefSection
    suggested_priorities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date.isoformat(),
            "generated_at": self.generated_at.isoformat(),
            "events_today": self.events_today.to_dict(),
            "events_upcoming": self.events_upcoming.to_dict(),
            "bills_due": self.bills_due.to_dict(),
            "followups_needed": self.followups_needed.to_dict(),
            "worth_checking": self.worth_checking.to_dict(),
            "carry_forward": self.carry_forward.to_dict(),
            "suggested_priorities": list(self.suggested_priorities),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DailyContext":
        return cls(
            date=date.fromisoformat(data["date"]),
            generated_at=datetime.fromisoformat(data["generated_at"]),
            events_today=PreBriefSection.from_dict(data["events_today"]),
            events_upcoming=PreBriefSection.from_dict(data["events_upcoming"]),
            bills_due=PreBriefSection.from_dict(data["bills_due"]),
            followups_needed=PreBriefSection.from_dict(data["followups_needed"]),
            worth_checking=PreBriefSection.from_dict(data["worth_checking"]),
            carry_forward=PreBriefSection.from_dict(data["carry_forward"]),
            suggested_priorities=list(data.get("suggested_priorities", [])),
        )

    @classmethod
    def from_json(cls, raw: str) -> "DailyContext":
        return cls.from_dict(json.loads(raw))

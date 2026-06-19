#!/usr/bin/env python3
"""
Check for upcoming appointments and return alerts.
Used by OpenClaw heartbeat to send proactive Telegram notifications.

Usage: python scripts/check_appointments.py
Output: JSON with any upcoming appointments within 48 hours
"""

import sys
import os
import json
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from second_brain.notes import list_all


def check_upcoming(hours_ahead: int = 48) -> list[dict]:
    """Return appointments due within the next N hours."""
    today = date.today()
    cutoff = today + timedelta(hours=hours_ahead / 24)

    appointments = list_all(item_type="Appointment", limit=200)
    upcoming = []

    for appt in appointments:
        date_str = appt.get("date", "").strip()
        if not date_str:
            continue
        try:
            appt_date = date.fromisoformat(date_str)
            if today <= appt_date <= cutoff:
                days_away = (appt_date - today).days
                upcoming.append({
                    "title": appt.get("title", "Untitled"),
                    "date": date_str,
                    "body": appt.get("body", ""),
                    "tags": appt.get("tags", ""),
                    "days_away": days_away,
                    "label": "today" if days_away == 0 else "tomorrow" if days_away == 1 else f"in {days_away} days",
                })
        except ValueError:
            continue

    upcoming.sort(key=lambda x: x["date"])
    return upcoming


if __name__ == "__main__":
    upcoming = check_upcoming(hours_ahead=48)
    print(json.dumps(upcoming, indent=2))
    if not upcoming:
        print("No upcoming appointments.", file=sys.stderr)

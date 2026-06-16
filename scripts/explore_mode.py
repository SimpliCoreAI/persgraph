#!/usr/bin/env python3
"""PersGraph Explore Mode helper.

Phase-1-ready plumbing with graceful fallback behavior when live location/POI
integrations are not yet available. This script is safe to run from cron.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/Los_Angeles")
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
STATE_PATH = DATA_DIR / "explore_state.json"
AUDIT_PATH = DATA_DIR / "explore_audit.json"

# Add second_brain to path for POI provider imports
sys.path.insert(0, str(ROOT))

# Import location/movement helpers
try:
    from explore_location import resolve_location_for_check, check_movement_and_suppress
    LOCATION_AVAILABLE = True
except ImportError:
    LOCATION_AVAILABLE = False
    resolve_location_for_check = lambda: None

DEFAULT_DURATION_MIN = 120
DEFAULT_CADENCE_MIN = 60
DEFAULT_INTENSITY = "medium"
VALID_INTENSITIES = {"low", "medium", "high"}
VALID_CADENCE = {30, 60, 90}
VALID_DURATION_KEYWORDS = {"2h", "4h", "8h", "eod", "trip"}


@dataclass
class ExploreSuggestion:
    title: str
    reason: str
    meal: str = ""
    tag: str = "explore"


def now_local() -> datetime:
    return datetime.now(LOCAL_TZ)


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _serialize_dt(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=LOCAL_TZ)
    except Exception:
        return None


def default_state() -> dict[str, Any]:
    return {
        "enabled": False,
        "started_at": None,
        "expires_at": None,
        "duration_label": "2h",
        "duration_minutes": DEFAULT_DURATION_MIN,
        "cadence_minutes": DEFAULT_CADENCE_MIN,
        "intensity": DEFAULT_INTENSITY,
        "last_suggestion_at": None,
        "last_check_at": None,
        "last_location": None,
        "session_suggestions": [],
        "suppression_cooldown_minutes": 15,
        "status": "idle",
    }


def load_state() -> dict[str, Any]:
    _ensure_data_dir()
    if not STATE_PATH.exists():
        state = default_state()
        save_state(state)
        return state
    try:
        data = json.loads(STATE_PATH.read_text())
    except Exception:
        data = default_state()
    merged = default_state()
    merged.update(data)
    return merged


def save_state(state: dict[str, Any]) -> None:
    _ensure_data_dir()
    STATE_PATH.write_text(json.dumps(state, indent=2))


def append_audit(event: dict[str, Any]) -> None:
    _ensure_data_dir()
    rows = []
    if AUDIT_PATH.exists():
        try:
            rows = json.loads(AUDIT_PATH.read_text())
        except Exception:
            rows = []
    rows.append(event)
    rows = rows[-200:]
    AUDIT_PATH.write_text(json.dumps(rows, indent=2))


def parse_duration(label: str | None) -> tuple[str, int | None]:
    label = (label or "2h").strip().lower()
    if label not in VALID_DURATION_KEYWORDS:
        return "2h", DEFAULT_DURATION_MIN
    mapping = {
        "2h": 120,
        "4h": 240,
        "8h": 480,
        "eod": None,
        "trip": None,
    }
    return label, mapping[label]


def end_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=23, minute=59, second=59, microsecond=0)


def enable_explore(duration: str | None, cadence: int | None, intensity: str | None) -> dict[str, Any]:
    state = load_state()
    started = now_local()
    duration_label, duration_minutes = parse_duration(duration)
    cadence_minutes = cadence if cadence in VALID_CADENCE else DEFAULT_CADENCE_MIN
    intensity_value = (intensity or DEFAULT_INTENSITY).strip().lower()
    if intensity_value not in VALID_INTENSITIES:
        intensity_value = DEFAULT_INTENSITY

    expires_at = None
    if duration_label == "eod":
        expires_at = end_of_day(started)
    elif duration_minutes is not None:
        expires_at = started + timedelta(minutes=duration_minutes)

    state.update(
        {
            "enabled": True,
            "started_at": _serialize_dt(started),
            "expires_at": _serialize_dt(expires_at),
            "duration_label": duration_label,
            "duration_minutes": duration_minutes,
            "cadence_minutes": cadence_minutes,
            "intensity": intensity_value,
            "last_suggestion_at": None,
            "last_check_at": None,
            "session_suggestions": [],
            "status": "active",
        }
    )
    save_state(state)
    append_audit({"at": _serialize_dt(started), "event": "enabled", "state": state})
    return state


def disable_explore(reason: str = "manual") -> dict[str, Any]:
    state = load_state()
    state.update({
        "enabled": False,
        "status": f"disabled:{reason}",
        "expires_at": state.get("expires_at"),
    })
    save_state(state)
    append_audit({"at": _serialize_dt(now_local()), "event": "disabled", "reason": reason})
    return state


def describe_duration(state: dict[str, Any]) -> str:
    label = state.get("duration_label", "2h")
    return {
        "2h": "2 hours",
        "4h": "4 hours",
        "8h": "8 hours",
        "eod": "until end of day",
        "trip": "for this trip",
    }.get(label, "2 hours")


def format_toggle_on(state: dict[str, Any]) -> str:
    return (
        "✅ Explore Mode: ON\n"
        f"⏱ Duration: {describe_duration(state)}\n"
        f"📍 Cadence: every {state.get('cadence_minutes', DEFAULT_CADENCE_MIN)} minutes\n"
        f"🎯 Intensity: {state.get('intensity', DEFAULT_INTENSITY)}\n"
        "🗺 Location-aware suggestions: active\n\n"
        "You'll get nearby ideas while Explore Mode is on."
    )


def format_toggle_off() -> str:
    return "🛑 Explore Mode: OFF\n\nNo more nearby suggestions will be sent."


def should_run_suggestion(state: dict[str, Any], now: datetime | None = None) -> tuple[bool, str]:
    now = now or now_local()
    if not state.get("enabled"):
        return False, "explore mode is off"

    expires_at = _parse_dt(state.get("expires_at"))
    if expires_at and now >= expires_at:
        disable_explore(reason="expired")
        return False, "explore mode expired"

    last_check = _parse_dt(state.get("last_check_at"))
    cadence = int(state.get("cadence_minutes") or DEFAULT_CADENCE_MIN)
    if last_check and now < last_check + timedelta(minutes=cadence):
        return False, "cadence window not reached"
    
    # Phase 2: Check movement since last location
    if LOCATION_AVAILABLE:
        current_loc = resolve_location_for_check()
        last_loc = state.get("last_location")
        moved_ok, reason = check_movement_and_suppress(current_loc, last_loc, state)
        if not moved_ok:
            return False, reason
    return True, "ok"


def _load_bucket_list_set() -> set[str]:
    """Load bucket-list item names (lowercase) as a set for fast lookup."""
    try:
        from second_brain.places_db import list_all
        items = list_all(limit=100)  # Load more, filter by tag
        bucket_items = [i for i in items if 'bucketlist' in (i.get('tags', '') or '').lower()]
        return {item.get('name', '').lower() for item in bucket_items}
    except Exception:
        return set()


def _get_nearby_poi_suggestion(location: dict[str, Any]) -> ExploreSuggestion | None:
    """
    Find a nearby high-rated POI (restaurant/cafe) with optional bucket-list boost.
    
    Location-first approach:
    1. Search nearby restaurants/cafes with good ratings
    2. Check if result is in bucket-list (bonus signal)
    3. Include bucket-list context if matched
    """
    try:
        from second_brain.poi_provider import Location, nearby_pois
        import urllib.parse

        # Parse location
        poi_location = Location(
            latitude=location.get("lat", 0),
            longitude=location.get("lon", 0),
            accuracy_m=location.get("accuracy_m"),
            source=location.get("source", "manual"),
        )

        # Get location-based POIs (primary signal)
        result = nearby_pois(
            location=poi_location,
            radius_meters=3000,
            query="restaurant cafe",
            limit=3,
            fallback_to_all=True,
        )

        if not result.pois:
            return None

        # Load bucket-list for optional boost signal
        bucket_names = _load_bucket_list_set()

        # Filter to high-quality POIs (rating >= 4.0 if available)
        # This ensures only good-vibe places are suggested
        quality_pois = [
            p for p in result.pois
            if p.rating is None or p.rating >= 4.0
        ]
        
        if not quality_pois:
            quality_pois = result.pois  # Fallback if no 4+ ratings
        
        # Pick the best POI (first in ranked list)
        poi = result.pois[0]
        
        # Build Google Maps link (use place_id if available via raw_data)
        if poi.raw_data and poi.raw_data.get('place_id'):
            maps_url = f"https://www.google.com/maps/place/?q=place_id:{poi.raw_data['place_id']}"
        else:
            # Fallback to search by name + address
            maps_query = f"{poi.name} {poi.address}".strip()
            maps_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote_plus(maps_query)}"
        
        # Format rating
        rating_str = f"{poi.rating}★" if poi.rating else "popular"
        
        # Check if in bucket-list (boost signal, not filter)
        in_bucket = poi.name.lower() in bucket_names
        bucket_suffix = " [saved in bucket-list]" if in_bucket else ""
        
        return ExploreSuggestion(
            title=f"{poi.name}{bucket_suffix}",
            reason=f"{rating_str} • {poi.distance_meters / 1000:.1f} km • {poi.address} 🗺 {maps_url}",
            meal=f"📍 {poi.category}",
            tag="poi",
        )
    except Exception as e:
        import logging
        logging.warning(f"POI lookup error: {e}")
        return None


def _fallback_suggestion() -> ExploreSuggestion:
    """Fallback when no location or POI data available."""
    return ExploreSuggestion(
        title="Explore Nearby",
        reason="Enable location access for personalized recommendations.",
        meal="Nearby restaurants, cafés, and spots",
        tag="fallback",
    )


def build_suggestion(state: dict[str, Any] | None = None) -> ExploreSuggestion:
    """
    Build suggestion: location-first POIs with optional bucket-list boost.
    
    Priority:
    1. Location-based POIs (primary) with bucket-list as boost signal
    2. Fallback if location not available
    """
    # Try location-based POI lookup (primary)
    if state:
        last_location = state.get("last_location")
        if last_location:
            suggestion = _get_nearby_poi_suggestion(last_location)
            if suggestion:
                return suggestion

    # Fallback when no location or POI results
    return _fallback_suggestion()


def format_suggestion_message(suggestion: ExploreSuggestion, state: dict[str, Any]) -> str:
    """Format suggestion for Telegram: concise and useful."""
    lines = ["🗺 Explore Nearby", f"📍 {suggestion.title}", f"{suggestion.reason}"]
    if suggestion.meal:
        lines.append(f"🍽 {suggestion.meal}")
    cadence = state.get("cadence_minutes", DEFAULT_CADENCE_MIN)
    lines.append(f"⏱ Next check ~{cadence}m")
    return "\n".join(lines)


def check_once() -> tuple[bool, str]:
    state = load_state()
    now = now_local()
    ok, reason = should_run_suggestion(state, now=now)
    state["last_check_at"] = _serialize_dt(now)
    
    # Update location cache for movement detection
    if LOCATION_AVAILABLE:
        current_loc = resolve_location_for_check()
        if current_loc:
            state["last_location"] = current_loc.to_dict()
    
    save_state(state)
    if not ok:
        append_audit({"at": _serialize_dt(now), "event": "skip", "reason": reason})
        return False, reason

    suggestion = build_suggestion(state=state)
    message = format_suggestion_message(suggestion, state)
    state["last_suggestion_at"] = _serialize_dt(now)
    session = list(state.get("session_suggestions") or [])
    session.append({"at": _serialize_dt(now), "title": suggestion.title, "tag": suggestion.tag})
    state["session_suggestions"] = session[-20:]
    save_state(state)
    append_audit({"at": _serialize_dt(now), "event": "suggestion", "title": suggestion.title, "tag": suggestion.tag})
    return True, message


def status_text() -> str:
    state = load_state()
    enabled = "ON" if state.get("enabled") else "OFF"
    lines = [f"Explore Mode: {enabled}"]
    lines.append(f"Duration: {describe_duration(state)}")
    lines.append(f"Cadence: every {state.get('cadence_minutes', DEFAULT_CADENCE_MIN)} min")
    lines.append(f"Intensity: {state.get('intensity', DEFAULT_INTENSITY)}")
    if state.get("last_suggestion_at"):
        lines.append(f"Last suggestion: {state['last_suggestion_at']}")
    if state.get("status"):
        lines.append(f"Status: {state['status']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="PersGraph Explore Mode helper")
    parser.add_argument("--check", action="store_true", help="Run one cron-safe suggestion check")
    parser.add_argument("--status", action="store_true", help="Print current explore status")
    args = parser.parse_args()

    if args.status:
        print(status_text())
        return 0
    if args.check:
        ok, msg = check_once()
        print(msg)
        return 0 if ok else 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

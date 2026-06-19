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
from dotenv import load_dotenv
from typing import Any
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/Los_Angeles")
ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data"
load_dotenv(ROOT / ".env.local")
load_dotenv(ROOT / ".env")
STATE_PATH = DATA_DIR / "explore_state.json"
AUDIT_PATH = DATA_DIR / "explore_audit.json"

# Add second_brain to path for POI provider imports
sys.path.insert(0, str(ROOT))

# Import location/movement helpers
try:
    from .explore_location import resolve_location_for_check, check_movement_and_suppress
    LOCATION_AVAILABLE = True
except ImportError:
    LOCATION_AVAILABLE = False
    resolve_location_for_check = lambda: None

# Import learning layer integration (Phase 2)
try:
    from second_brain.learning_explore_integration import (
        on_explore_enabled,
        on_explore_disabled,
        on_skip_event,
        on_suggestion_offered,
    )
    LEARNING_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    LEARNING_AVAILABLE = False
    # Graceful fallbacks for learning hooks
    on_explore_enabled = lambda **kwargs: None
    on_explore_disabled = lambda *args, **kwargs: None
    on_skip_event = lambda **kwargs: None
    on_suggestion_offered = lambda **kwargs: None

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
        "session_id": None,
        "last_event_id": None,
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
    
    # Phase 2: Record learning event for session enabled
    if LEARNING_AVAILABLE:
        try:
            session_id = on_explore_enabled(
                duration_label=duration_label,
                cadence_minutes=cadence_minutes,
                intensity=intensity_value,
                location=state.get("last_location")
            )
            state["session_id"] = session_id
            save_state(state)
        except Exception as e:
            import logging
            logging.warning(f"Learning layer error in enable_explore: {e}")
    
    append_audit({"at": _serialize_dt(started), "event": "enabled", "state": state})
    return state


def disable_explore(reason: str = "manual") -> dict[str, Any]:
    state = load_state()
    session_id = state.get("session_id")
    
    # Phase 2: Record learning event for session disabled
    if LEARNING_AVAILABLE and session_id:
        try:
            on_explore_disabled(session_id, reason=reason)
        except Exception as e:
            import logging
            logging.warning(f"Learning layer error in disable_explore: {e}")
    
    state.update({
        "enabled": False,
        "status": f"disabled:{reason}",
        "expires_at": state.get("expires_at"),
    })
    save_state(state)
    append_audit({"at": _serialize_dt(now_local()), "event": "disabled", "reason": reason})
    return state


def describe_duration(state: dict[str, Any]) -> str:
    minutes = state.get("duration_minutes")
    if minutes == 120:
        return "2 hours"
    if minutes == 240:
        return "4 hours"
    if minutes == 480:
        return "8 hours"
    if minutes is None and state.get("duration_label") == "eod":
        return "until end of day"
    if minutes is None and state.get("duration_label") == "trip":
        return "for this trip"
    if isinstance(minutes, (int, float)) and minutes > 0:
        hours = minutes / 60
        return f"{hours:g} hours"
    return "2 hours"


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

    last_suggestion = _parse_dt(state.get("last_suggestion_at"))
    cadence = int(state.get("cadence_minutes") or DEFAULT_CADENCE_MIN)
    if last_suggestion and now < last_suggestion + timedelta(minutes=cadence):
        # Phase 2: Record skip event for cadence window not reached
        if LEARNING_AVAILABLE:
            try:
                on_skip_event(reason="cadence_window_not_reached", explore_session_id=state.get("session_id"), location=state.get("last_location"))
            except Exception as e:
                import logging
                logging.warning(f"Learning layer error in should_run_suggestion cadence skip: {e}")
        return False, "cadence window not reached"
    
    # Phase 2: Check movement since last location
    if LOCATION_AVAILABLE:
        current_loc = resolve_location_for_check()
        last_loc = state.get("last_location")
        moved_ok, reason = check_movement_and_suppress(current_loc, last_loc, state)
        if not moved_ok:
            # Record skip event in learning layer if available
            if LEARNING_AVAILABLE:
                try:
                    on_skip_event(reason=reason, explore_session_id=state.get("session_id"), location=current_loc.to_dict() if current_loc else None)
                except Exception as e:
                    import logging
                    logging.warning(f"Learning layer error in should_run_suggestion movement skip: {e}")
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

        # Build two result sets so the message always balances food + places-to-see.
        food_result = nearby_pois(
            location=poi_location,
            radius_meters=5000,
            query="restaurant cafe bakery coffee",
            limit=5,
            fallback_to_all=False,
        )
        scenic_result = nearby_pois(
            location=poi_location,
            radius_meters=7000,
            query="park landmark attraction museum viewpoint scenic trail garden",
            limit=5,
            fallback_to_all=False,
        )

        if not food_result.pois and not scenic_result.pois:
            return None

        # Load bucket-list for optional boost signal (reference only)
        bucket_names = _load_bucket_list_set()

        def quality_pick(items):
            filtered = [p for p in items if p.rating is None or p.rating >= 3.8]
            return filtered[:3] if filtered else items[:3]

        food_pois = quality_pick(food_result.pois)
        scenic_pois = quality_pick(scenic_result.pois)
        lines: list[str] = []

        def format_line(poi):
            if poi.raw_data and poi.raw_data.get('place_id'):
                maps_url = f"https://www.google.com/maps/place/?q=place_id:{poi.raw_data['place_id']}"
            else:
                maps_query = f"{poi.name} {poi.address}".strip()
                maps_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote_plus(maps_query)}"
            rating_str = f"{poi.rating}★" if poi.rating else "popular"
            in_bucket = poi.name.lower() in bucket_names
            bucket_suffix = " [saved in bucket-list]" if in_bucket else ""
            return f"• {poi.name}{bucket_suffix} — {rating_str} • {poi.distance_meters / 1000:.1f} km • {poi.address} 🗺 {maps_url}"

        if food_pois:
            lines.append("🍽 Food options nearby")
            for poi in food_pois[:2]:
                lines.append(format_line(poi))

        if scenic_pois:
            lines.append("🗺 Places to see nearby")
            for poi in scenic_pois[:2]:
                lines.append(format_line(poi))

        combined = food_pois[:1] + scenic_pois[:1]
        title = combined[0].name if combined else (food_pois[0].name if food_pois else scenic_pois[0].name)
        meal = f"📍 {combined[0].category if combined else (food_pois[0].category if food_pois else scenic_pois[0].category)}"
        return ExploreSuggestion(
            title=title,
            reason="\n".join(lines),
            meal=meal,
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
    title = suggestion.title.replace(" [saved in bucket-list]", "")
    reason = suggestion.reason.replace(" [saved in bucket-list]", "")
    if "bucket-list" in reason.lower():
        reason = reason.replace(" [saved in bucket-list]", "")
    lines = ["🗺 Explore Nearby", f"📍 {title}"]
    event_id = state.get("last_event_id")
    if event_id:
        lines.append(f"🆔 Event ID: `{event_id}`")
    lines.append(f"{reason}")
    if suggestion.meal:
        meal = suggestion.meal.replace("📍 ", "").strip()
        if meal:
            lines.append(f"🍽 {meal}")
    cadence = state.get("cadence_minutes", DEFAULT_CADENCE_MIN)
    lines.append(f"⏱ Next check in ~{cadence}m")
    return "\n".join(lines)




def format_feedback_message(event_id: str) -> str:
    return f"🆔 Explore Event ID: `{event_id}`"


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
    
    # Phase 2: Record learning event for suggestion offered
    event_id = None
    if LEARNING_AVAILABLE:
        try:
            event_id = on_suggestion_offered(
                suggestion_title=suggestion.title,
                suggestion_category=suggestion.tag,
                cadence_minutes=state.get("cadence_minutes", DEFAULT_CADENCE_MIN),
                intensity=state.get("intensity", DEFAULT_INTENSITY),
                location=state.get("last_location"),
                explore_session_id=state.get("session_id")
            )
            state["last_event_id"] = event_id
        except Exception as e:
            import logging
            logging.warning(f"Learning layer error in check_once suggestion: {e}")
    
    state["last_suggestion_at"] = _serialize_dt(now)
    session = list(state.get("session_suggestions") or [])
    session.append({"at": _serialize_dt(now), "title": suggestion.title, "tag": suggestion.tag})
    state["session_suggestions"] = session[-20:]
    save_state(state)
    append_audit({"at": _serialize_dt(now), "event": "suggestion", "title": suggestion.title, "tag": suggestion.tag})
    if event_id:
        return True, message + "\n\n" + format_feedback_message(event_id)
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

"""
Explore Mode State Management

Handles persistence and manipulation of explore_state.json.
Provides helpers for enabling/disabling, updating cadence, checking expiry, etc.

State file: data/explore_state.json
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/Los_Angeles")

STATE_FILE = Path(__file__).parent.parent / "data" / "explore_state.json"


def _now_local() -> datetime:
    """Get current time in local timezone."""
    return datetime.now(LOCAL_TZ)


def _ensure_state_dir() -> None:
    """Create data directory if needed."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_state() -> dict[str, Any]:
    """Load explore state from disk. Returns default state if file missing."""
    _ensure_state_dir()
    if not STATE_FILE.exists():
        return _default_state()
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return _default_state()


def save_state(state: dict[str, Any]) -> None:
    """Persist state to disk."""
    _ensure_state_dir()
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2, default=str)


def _default_state() -> dict[str, Any]:
    """Return blank initial state."""
    return {
        "enabled": False,
        "started_at": None,
        "duration_minutes": 120,
        "cadence_minutes": 60,
        "intensity": "medium",
        "last_suggestion_at": None,
        "last_location": {
            "lat": None,
            "lon": None,
            "source": None,
            "accuracy_m": None,
            "city": None
        },
        "suppression_cooldown_minutes": 15,
        "suggested_places_session": [],
        "suppression_history": {},  # Phase 2: track 4h dedup
        "movement_threshold_km": 1.0,  # Phase 2: only trigger on significant move
        "phase": "1",
        "audit_trail": []
    }


def enable_explore(
    duration_str: str = "2h",
    cadence_str: str = "60m",
    intensity: str = "medium"
) -> dict[str, Any]:
    """
    Enable Explore Mode with the given parameters.
    
    Duration formats:
      "2h", "4h", "8h" -> minutes
      "eod"            -> minutes until end of day
      "trip"           -> indefinite (None)
      
    Cadence formats:
      "30m", "60m", "90m", "120m" -> minutes
      
    Intensity:
      "low", "medium", "high"
    """
    state = load_state()
    now = _now_local()
    
    # Parse duration
    duration_minutes = _parse_duration(duration_str)
    if duration_minutes is None and duration_str.lower() != "trip":
        duration_minutes = 120  # fallback
    
    # Parse cadence
    cadence_minutes = _parse_cadence(cadence_str)
    if cadence_minutes is None:
        cadence_minutes = 60  # fallback
    
    # Validate intensity
    if intensity not in ("low", "medium", "high"):
        intensity = "medium"
    
    state["enabled"] = True
    state["started_at"] = now.isoformat()
    state["duration_minutes"] = duration_minutes
    state["cadence_minutes"] = cadence_minutes
    state["intensity"] = intensity
    state["last_suggestion_at"] = None
    state["suggested_places_session"] = []
    state["suppression_history"] = {}
    state["audit_trail"].append({
        "timestamp": now.isoformat(),
        "event": "enable",
        "duration_minutes": duration_minutes,
        "cadence_minutes": cadence_minutes,
        "intensity": intensity
    })
    
    save_state(state)
    return state


def disable_explore() -> dict[str, Any]:
    """Disable Explore Mode immediately."""
    state = load_state()
    now = _now_local()
    state["enabled"] = False
    state["audit_trail"].append({
        "timestamp": now.isoformat(),
        "event": "disable"
    })
    save_state(state)
    return state


def is_enabled() -> bool:
    """Check if Explore Mode is currently enabled."""
    state = load_state()
    return state.get("enabled", False)


def is_expired() -> bool:
    """Check if the enabled session has expired."""
    state = load_state()
    if not state.get("enabled"):
        return False
    
    started_at_str = state.get("started_at")
    if not started_at_str:
        return False
    
    duration_minutes = state.get("duration_minutes")
    if duration_minutes is None:  # "trip" mode = indefinite
        return False
    
    try:
        started_at = datetime.fromisoformat(started_at_str)
        expiry = started_at + timedelta(minutes=duration_minutes)
        return _now_local() >= expiry
    except (ValueError, TypeError):
        return False


def should_suggest_now() -> bool:
    """Check if enough time has passed since last suggestion to trigger again."""
    state = load_state()
    if not state.get("enabled"):
        return False
    
    if is_expired():
        disable_explore()
        return False
    
    last_suggestion_str = state.get("last_suggestion_at")
    if not last_suggestion_str:
        return True  # First time
    
    try:
        last_suggestion = datetime.fromisoformat(last_suggestion_str)
        cadence_minutes = state.get("cadence_minutes", 60)
        now = _now_local()
        return (now - last_suggestion) >= timedelta(minutes=cadence_minutes)
    except (ValueError, TypeError):
        return True


def mark_suggestion_sent(place_ids: list[str] = None) -> None:
    """Update state after a suggestion has been sent."""
    state = load_state()
    now = _now_local()
    state["last_suggestion_at"] = now.isoformat()
    if place_ids:
        state["suggested_places_session"].extend(place_ids)
        # Phase 2: keep last 20 in session to avoid immediate repeats
        state["suggested_places_session"] = state["suggested_places_session"][-20:]
    state["audit_trail"].append({
        "timestamp": now.isoformat(),
        "event": "suggestion_sent",
        "places": place_ids or []
    })
    save_state(state)


def update_location(lat: float, lon: float, source: str = "device_gps", accuracy_m: int = None, city: str = None) -> None:
    """Store the last known location."""
    state = load_state()
    state["last_location"] = {
        "lat": lat,
        "lon": lon,
        "source": source,
        "accuracy_m": accuracy_m,
        "city": city
    }
    state["audit_trail"].append({
        "timestamp": _now_local().isoformat(),
        "event": "location_update",
        "lat": lat,
        "lon": lon,
        "source": source
    })
    save_state(state)


def get_location() -> dict[str, Any] | None:
    """Get the last known location, or None if not set."""
    state = load_state()
    loc = state.get("last_location")
    if loc and loc.get("lat") is not None and loc.get("lon") is not None:
        return loc
    return None


def _parse_duration(duration_str: str) -> int | None:
    """Parse duration string into minutes. Returns None for 'trip' mode."""
    s = (duration_str or "").strip().lower()
    if not s:
        return 120  # default
    
    if s == "trip":
        return None  # indefinite
    
    if s == "eod":
        # Calculate minutes until midnight
        now = _now_local()
        midnight = now.replace(hour=23, minute=59, second=59, microsecond=0)
        delta = midnight - now
        return int(delta.total_seconds() / 60)
    
    # Try to match "2h", "4h", "30m", "90m" etc.
    import re
    m = re.match(r'^(\d+)\s*([hm])$', s)
    if m:
        qty = int(m.group(1))
        unit = m.group(2)
        if unit == 'h':
            return qty * 60
        else:  # m
            return qty
    
    return None


def _parse_cadence(cadence_str: str) -> int | None:
    """Parse cadence string into minutes."""
    s = (cadence_str or "").strip().lower()
    if not s:
        return 60  # default
    
    # Match "30m", "60m", "90m", "120m"
    import re
    m = re.match(r'^(\d+)\s*m$', s)
    if m:
        return int(m.group(1))
    
    return None


def get_suppression_expired_places(hours: int = 4) -> list[str]:
    """
    Phase 2: Return list of places whose 4-hour (or custom) suppression has expired.
    Used to clear old dedups so they can be suggested again.
    """
    state = load_state()
    now = _now_local()
    suppression_history = state.get("suppression_history", {})
    expired = []
    
    for place_id, timestamp_str in list(suppression_history.items()):
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            if (now - timestamp) > timedelta(hours=hours):
                expired.append(place_id)
                del suppression_history[place_id]
        except (ValueError, TypeError):
            pass
    
    if expired:
        save_state(state)
    return expired


def mark_place_suppressed(place_id: str) -> None:
    """
    Phase 2: Mark a place as suppressed for the next 4 hours.
    """
    state = load_state()
    if "suppression_history" not in state:
        state["suppression_history"] = {}
    state["suppression_history"][place_id] = _now_local().isoformat()
    save_state(state)


def format_state_summary() -> str:
    """Return a human-readable summary of current state (for debugging/logging)."""
    state = load_state()
    enabled = state.get("enabled", False)
    
    if not enabled:
        return "🛑 Explore Mode: OFF"
    
    duration_min = state.get("duration_minutes")
    duration_str = "trip (indefinite)" if duration_min is None else f"{duration_min} min"
    
    cadence_min = state.get("cadence_minutes", 60)
    intensity = state.get("intensity", "medium")
    started_at = state.get("started_at")
    
    lines = [
        "✅ Explore Mode: ON",
        f"⏱ Duration: {duration_str}",
        f"📍 Cadence: every {cadence_min} min",
        f"🎯 Intensity: {intensity}",
    ]
    
    if started_at:
        lines.append(f"🕐 Started: {started_at}")
    
    if is_expired():
        lines.append("⚠️  **EXPIRED** (will disable on next check)")
    
    last_sugg = state.get("last_suggestion_at")
    if last_sugg:
        lines.append(f"💬 Last suggestion: {last_sugg}")
    
    return "\n".join(lines)

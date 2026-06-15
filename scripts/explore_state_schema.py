#!/usr/bin/env python3
"""
Explore Mode — Data File Schema & State Utilities

Manages the explore_state.json file and ensures it conforms to the specification.
Safe defaults and graceful degradation if location/POI integrations are missing.

Schema: data/explore_state.json
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any, Optional

LOCAL_TZ = ZoneInfo("America/Los_Angeles")
STATE_FILE = Path(__file__).parent.parent / "data" / "explore_state.json"


def _now_iso() -> str:
    """Current time in ISO format with timezone."""
    return datetime.now(LOCAL_TZ).isoformat()


def default_state() -> dict[str, Any]:
    """Return a clean default explore state."""
    return {
        "enabled": False,
        "started_at": None,
        "duration_minutes": 120,  # default: 2 hours
        "cadence_minutes": 60,     # default: every 60 minutes
        "intensity": "medium",     # low | medium | high
        "last_suggestion_at": None,
        "last_location": None,     # {"lat": float, "lon": float, "source": str, "accuracy_m": int}
        "suppression_cooldown_minutes": 15,
        "suggested_places_session": [],  # list of place IDs to suppress in this session
        "suppression_history": {},  # {place_id: timestamp} for longer suppression
    }


def load_state() -> dict[str, Any]:
    """Load state from disk, or return default if missing."""
    if not STATE_FILE.exists():
        return default_state()
    try:
        with open(STATE_FILE) as f:
            data = json.load(f)
        # Validate top-level keys exist
        template = default_state()
        for key in template:
            if key not in data:
                data[key] = template[key]
        return data
    except (json.JSONDecodeError, IOError):
        return default_state()


def save_state(state: dict[str, Any]) -> bool:
    """Persist state to disk. Returns success bool."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
        return True
    except Exception as e:
        print(f"⚠️ Failed to save explore state: {e}")
        return False


def is_enabled() -> bool:
    """Quick check: is Explore Mode currently active?"""
    state = load_state()
    if not state.get("enabled"):
        return False
    # Check if duration has expired
    started = state.get("started_at")
    duration = state.get("duration_minutes", 120)
    if not started or duration is None:
        return False
    try:
        start_dt = datetime.fromisoformat(started)
        elapsed_minutes = (datetime.now(LOCAL_TZ) - start_dt).total_seconds() / 60
        if elapsed_minutes > duration:
            return False
    except (ValueError, TypeError):
        return False
    return True


def should_trigger_suggestion() -> bool:
    """
    Check if a suggestion should be triggered based on cadence.
    Returns True if enough time has passed since last suggestion.
    """
    state = load_state()
    if not is_enabled():
        return False
    
    last_suggest = state.get("last_suggestion_at")
    cadence = state.get("cadence_minutes", 60)
    
    if not last_suggest:
        return True
    
    try:
        last_dt = datetime.fromisoformat(last_suggest)
        elapsed_minutes = (datetime.now(LOCAL_TZ) - last_dt).total_seconds() / 60
        return elapsed_minutes >= cadence
    except (ValueError, TypeError):
        return True


def update_last_suggestion() -> None:
    """Record the time of the last suggestion."""
    state = load_state()
    state["last_suggestion_at"] = _now_iso()
    save_state(state)


def update_location(lat: float, lon: float, source: str = "manual", accuracy_m: int = 50) -> None:
    """Update the current location."""
    state = load_state()
    state["last_location"] = {
        "lat": lat,
        "lon": lon,
        "source": source,
        "accuracy_m": accuracy_m,
    }
    save_state(state)


def get_current_location() -> Optional[dict[str, Any]]:
    """Get the last known location, or None if unavailable."""
    state = load_state()
    return state.get("last_location")


def add_to_session_suppression(place_id: str) -> None:
    """Add a place to session-level suppression."""
    state = load_state()
    if place_id not in state["suggested_places_session"]:
        state["suggested_places_session"].append(place_id)
    save_state(state)


def is_suppressed(place_id: str, cooldown_hours: int = 4) -> bool:
    """
    Check if a place is currently suppressed.
    Session suppression: 15 min (fast decay)
    History suppression: up to cooldown_hours (default 4)
    """
    state = load_state()
    
    # Session suppression (active for this Explore Mode session)
    if place_id in state.get("suggested_places_session", []):
        return True
    
    # History suppression (longer-term dedup)
    history = state.get("suppression_history", {})
    if place_id in history:
        try:
            last_time = datetime.fromisoformat(history[place_id])
            age_hours = (datetime.now(LOCAL_TZ) - last_time).total_seconds() / 3600
            if age_hours < cooldown_hours:
                return True
        except (ValueError, TypeError):
            pass
    
    return False


def mark_suppressed(place_id: str) -> None:
    """Mark a place as suppressed in history."""
    state = load_state()
    state.setdefault("suppression_history", {})[place_id] = _now_iso()
    save_state(state)


def reset_session_suppression() -> None:
    """Clear session suppression (but keep history). Called when Explore Mode is disabled."""
    state = load_state()
    state["suggested_places_session"] = []
    save_state(state)


# Validation & schema helpers
def validate_state(state: dict[str, Any]) -> list[str]:
    """
    Validate a state dict against the schema.
    Returns list of validation errors (empty if valid).
    """
    errors = []
    
    if not isinstance(state.get("enabled"), bool):
        errors.append("'enabled' must be a boolean")
    
    if state.get("duration_minutes") is not None:
        if not isinstance(state["duration_minutes"], (int, float)) or state["duration_minutes"] < 0:
            errors.append("'duration_minutes' must be a non-negative number")
    
    if state.get("cadence_minutes") is not None:
        if not isinstance(state["cadence_minutes"], (int, float)) or state["cadence_minutes"] < 1:
            errors.append("'cadence_minutes' must be >= 1")
    
    if state.get("intensity") not in (None, "low", "medium", "high"):
        errors.append("'intensity' must be 'low', 'medium', or 'high'")
    
    if state.get("last_location") is not None:
        loc = state["last_location"]
        if not isinstance(loc, dict):
            errors.append("'last_location' must be a dict or null")
        else:
            if not isinstance(loc.get("lat"), (int, float)):
                errors.append("'last_location.lat' must be a number")
            if not isinstance(loc.get("lon"), (int, float)):
                errors.append("'last_location.lon' must be a number")
    
    if state.get("suggested_places_session") is not None:
        if not isinstance(state["suggested_places_session"], list):
            errors.append("'suggested_places_session' must be a list")
    
    return errors


if __name__ == "__main__":
    # Quick smoke test
    print("📋 Explore Mode State Schema")
    print(f"File: {STATE_FILE}")
    print(f"Enabled: {is_enabled()}")
    print(f"Should trigger: {should_trigger_suggestion()}")
    state = load_state()
    errors = validate_state(state)
    if errors:
        print(f"⚠️ Validation errors:")
        for err in errors:
            print(f"  - {err}")
    else:
        print("✅ State is valid")
    print(f"\nCurrent state:\n{json.dumps(state, indent=2)}")

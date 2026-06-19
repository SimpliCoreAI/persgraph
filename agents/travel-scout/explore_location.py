#!/usr/bin/env python3
"""
Explore Mode — Location & Movement Detection

Handles:
  - Device location lookup (OpenClaw node integration if available)
  - Fallback to manual/saved location
  - Movement detection to suppress redundant suggestions
  - Graceful degradation when location unavailable

Safe cron-ready: all location sources fail gracefully.
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/Los_Angeles")
ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data"
LOCATION_CACHE = DATA_DIR / "explore_location_cache.json"


class Location:
    """Represents a geographic point."""
    
    def __init__(
        self,
        lat: float,
        lon: float,
        source: str = "manual",
        accuracy_m: int = 50,
        timestamp: Optional[datetime] = None,
    ):
        self.lat = lat
        self.lon = lon
        self.source = source  # device_gps, manual, saved_context, fallback
        self.accuracy_m = accuracy_m
        self.timestamp = timestamp or datetime.now(LOCAL_TZ)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "lat": self.lat,
            "lon": self.lon,
            "source": self.source,
            "accuracy_m": self.accuracy_m,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Location:
        ts_str = data.get("timestamp")
        ts = None
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str)
            except Exception:
                pass
        return cls(
            lat=float(data["lat"]),
            lon=float(data["lon"]),
            source=data.get("source", "manual"),
            accuracy_m=int(data.get("accuracy_m", 50)),
            timestamp=ts,
        )
    
    def __str__(self) -> str:
        return f"({self.lat:.4f}, {self.lon:.4f}) [{self.source}]"


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def distance_haversine(loc1: Location, loc2: Location) -> float:
    """
    Compute distance in meters between two locations.
    Uses Haversine formula.
    """
    R = 6371000  # Earth radius in meters
    
    lat1_rad = math.radians(loc1.lat)
    lat2_rad = math.radians(loc2.lat)
    delta_lat = math.radians(loc2.lat - loc1.lat)
    delta_lon = math.radians(loc2.lon - loc1.lon)
    
    a = (
        math.sin(delta_lat / 2) ** 2 +
        math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


def try_openclaw_location() -> Optional[Location]:
    """
    Attempt to fetch device location from OpenClaw node integration.
    
    Returns:
        Location if available, None if unavailable or integration not set up.
    
    Integration points:
      1. Check for OPENCLAW_LOCATION_API env var (optional HTTP endpoint)
      2. Check for local device data in PersGraph's node sync (future)
      3. Gracefully fail and return None
    """
    try:
        # Placeholder: future integration with OpenClaw node API
        # For now, check if there's a manual override in env
        loc_override = os.environ.get("EXPLORE_LOCATION_OVERRIDE")
        if loc_override:
            # Format: "lat,lon" or "lat,lon,source"
            parts = loc_override.split(",")
            if len(parts) >= 2:
                try:
                    lat = float(parts[0].strip())
                    lon = float(parts[1].strip())
                    source = parts[2].strip() if len(parts) > 2 else "device_override"
                    return Location(lat=lat, lon=lon, source=source, accuracy_m=10)
                except (ValueError, IndexError):
                    pass
        
        # Future: Try OpenClaw node integration here
        # if OPENCLAW_AVAILABLE:
        #     node_data = get_device_location_from_openclaw()
        #     if node_data:
        #         return Location(lat=..., lon=..., source="device_gps", accuracy_m=...)
        
        return None
    except Exception as e:
        print(f"⚠️ OpenClaw location lookup failed (OK in degraded mode): {e}")
        return None


def try_saved_location() -> Optional[Location]:
    """
    Load last known good location from cache.
    Returns None if cache unavailable or stale (>24h).
    """
    try:
        if not LOCATION_CACHE.exists():
            return None
        
        data = json.loads(LOCATION_CACHE.read_text())
        if not data:
            return None
        
        loc = Location.from_dict(data)
        
        # Check staleness: if >24h old, don't use
        age_seconds = (datetime.now(LOCAL_TZ) - loc.timestamp).total_seconds()
        if age_seconds > 86400:  # 24 hours
            return None
        
        return loc
    except Exception as e:
        print(f"⚠️ Could not load saved location (OK in degraded mode): {e}")
        return None


def get_current_location() -> Optional[Location]:
    """
    Resolve current location via preference chain:
      1. OpenClaw device GPS
      2. Manual override (env var)
      3. Saved/cached location
      4. None (degrade gracefully)
    """
    # Try device first
    device_loc = try_openclaw_location()
    if device_loc:
        save_location_cache(device_loc)
        return device_loc
    
    # Fall back to saved
    saved_loc = try_saved_location()
    return saved_loc


def save_location_cache(location: Location) -> None:
    """Cache current location for fallback."""
    _ensure_data_dir()
    try:
        LOCATION_CACHE.write_text(json.dumps(location.to_dict(), indent=2))
    except Exception as e:
        print(f"⚠️ Could not save location cache: {e}")


def has_moved_enough(
    current_location: Optional[Location],
    last_location: Optional[dict[str, Any]],
    min_distance_m: int = 500,
) -> bool:
    """
    Check if user has moved far enough since last suggestion.
    
    Args:
        current_location: Current location (can be None)
        last_location: Last known location from explore state (dict or None)
        min_distance_m: Minimum distance in meters to suppress re-suggestion
    
    Returns:
        True if moved enough OR location unavailable (don't suppress on missing data)
        False only if we have both locations and distance < threshold
    """
    if current_location is None:
        # Can't verify movement, don't suppress
        return True
    
    if last_location is None:
        # No prior location to compare, allow suggestion
        return True
    
    try:
        last_loc = Location.from_dict(last_location)
        distance_m = distance_haversine(current_location, last_loc)
        return distance_m >= min_distance_m
    except Exception:
        # If comparison fails, allow suggestion
        return True


def format_location_str(location: Optional[Location]) -> str:
    """Format a location for logging/display."""
    if not location:
        return "unavailable"
    return f"{location.lat:.4f},{location.lon:.4f} ({location.source}, ±{location.accuracy_m}m)"


# ─────────────────────────────────────────────────────────────────────────────
# Public API for Explore Mode Integration
# ─────────────────────────────────────────────────────────────────────────────

def resolve_location_for_check() -> Optional[Location]:
    """
    Main entry point for explore_mode.py to get current location.
    Returns None if unavailable (safe degradation).
    """
    return get_current_location()


def check_movement_and_suppress(
    current_loc: Optional[Location],
    last_loc: Optional[dict[str, Any]],
    state: dict[str, Any],
) -> tuple[bool, str]:
    """
    Check if user has moved enough to warrant a new suggestion.
    
    Args:
        current_loc: Current location or None
        last_loc: Last location dict from state or None
        state: Full explore_state dict for intensity/context
    
    Returns:
        (should_suggest, reason_string)
    """
    intensity = state.get("intensity", "medium")
    
    # Map intensity to movement threshold
    thresholds_m = {
        "low": 1000,      # Must move 1km
        "medium": 500,    # Must move 500m (default)
        "high": 200,      # Must move 200m
    }
    threshold = thresholds_m.get(intensity, 500)
    
    if not has_moved_enough(current_loc, last_loc, min_distance_m=threshold):
        return False, f"user has not moved {threshold}m since last suggestion"
    
    return True, "movement check passed"


if __name__ == "__main__":
    # Smoke test
    print("📍 Explore Mode Location — Smoke Test")
    
    loc = get_current_location()
    if loc:
        print(f"✅ Current location: {loc}")
    else:
        print("⚠️ No location available (OK in test mode)")
    
    # Test movement
    last = {"lat": 37.7749, "lon": -122.4194} if loc else None
    current = Location(lat=37.776, lon=-122.419) if loc else None
    
    if current and last:
        moved = has_moved_enough(current, last, min_distance_m=100)
        print(f"✅ Moved enough (>100m)? {moved}")
    
    print("✅ Smoke test passed!")

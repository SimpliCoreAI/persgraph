#!/usr/bin/env python3
"""
Explore Mode — Suggestion & Formatting Helpers

Core logic skeleton for:
  - Nearby POI ranking (with graceful degradation)
  - Suggestion formatting for Telegram
  - Ranking placeholders for distance, relevance, weather
  - Integration with places/bucket-list when available

Safe: all POI/location integrations fail gracefully if unavailable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/Los_Angeles")


# ─────────────────────────────────────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Location:
    """Represents a geographic point."""
    lat: float
    lon: float
    name: Optional[str] = None
    source: str = "manual"  # device_gps, manual, saved_context
    accuracy_m: Optional[int] = None
    
    def __str__(self) -> str:
        return f"({self.lat:.4f}, {self.lon:.4f})"


@dataclass
class POI:
    """Point of Interest suggestion."""
    id: str
    name: str
    category: str  # Landmark, Restaurant, Cafe, Park, etc.
    distance_km: float
    open_now: Optional[bool] = None
    rating: Optional[float] = None
    notes: str = ""
    maps_url: str = ""
    is_saved_place: bool = False
    is_bucket_list: bool = False
    weather_fit: Optional[str] = None  # "indoor", "outdoor", "weather_dependent"
    suggested_duration_min: Optional[int] = None
    
    def rank_score(self, intensity: str = "medium") -> float:
        """
        Placeholder ranking score (0-100).
        Phase 2+ will incorporate weather, preferences, movement detection, etc.
        """
        score = 50.0  # baseline
        
        # Distance penalty (closer = better, but not abs critical for exploration)
        if self.distance_km <= 1.0:
            score += 15
        elif self.distance_km <= 2.5:
            score += 10
        elif self.distance_km <= 5.0:
            score += 5
        
        # Category boost
        popular_categories = ["Landmark", "Park", "Cafe", "Restaurant"]
        if self.category in popular_categories:
            score += 8
        
        # Saved/bucket-list boost
        if self.is_bucket_list:
            score += 25
        elif self.is_saved_place:
            score += 12
        
        # Open status
        if self.open_now:
            score += 5
        elif self.open_now is False:
            score -= 15
        
        # Rating (if available)
        if self.rating and self.rating >= 4.0:
            score += 8
        
        # Intensity modulation
        if intensity == "high":
            score *= 1.1
        elif intensity == "low":
            score *= 0.9
        
        return min(100.0, max(0.0, score))


@dataclass
class Suggestion:
    """A formatted suggestion ready to send."""
    primary_poi: POI
    secondary_poi: Optional[POI] = None  # e.g., nearby meal/cafe
    suggestion_type: str = "general"  # general, bucket_list_match, weather_friendly, family_friendly
    context: str = ""  # Additional context (weather, time fit, etc.)
    confidence: float = 0.5  # 0-1 likelihood of user interest
    
    def confidence_pct(self) -> int:
        return int(self.confidence * 100)


# ─────────────────────────────────────────────────────────────────────────────
# Suggestion Logic (Phase 1 skeleton)
# ─────────────────────────────────────────────────────────────────────────────

def rank_nearby_pois(
    pois: list[POI],
    intensity: str = "medium",
    suppress_ids: Optional[list[str]] = None,
) -> list[POI]:
    """
    Rank nearby POIs by relevance.
    
    Args:
        pois: List of candidate POIs
        intensity: "low", "medium", "high"
        suppress_ids: Place IDs to filter out
    
    Returns:
        Ranked list (best first)
    """
    suppress_ids = suppress_ids or []
    
    # Filter out suppressed
    filtered = [p for p in pois if p.id not in suppress_ids]
    
    # Score each
    scored = [(p, p.rank_score(intensity)) for p in filtered]
    
    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)
    
    return [p for p, score in scored]


def select_best_suggestion(
    ranked_pois: list[POI],
    intensity: str = "medium",
) -> Optional[Suggestion]:
    """
    Pick the best suggestion from ranked POIs.
    Returns None if no suitable option.
    """
    if not ranked_pois:
        return None
    
    primary = ranked_pois[0]
    secondary = ranked_pois[1] if len(ranked_pois) > 1 else None
    
    # Determine suggestion type
    if primary.is_bucket_list:
        suggestion_type = "bucket_list_match"
    else:
        suggestion_type = "general"
    
    # Confidence based on primary POI score
    confidence = primary.rank_score(intensity) / 100.0
    
    return Suggestion(
        primary_poi=primary,
        secondary_poi=secondary,
        suggestion_type=suggestion_type,
        context="",
        confidence=confidence,
    )


def enrich_with_saved_places(pois: list[POI], saved_place_ids: Optional[list[str]] = None) -> list[POI]:
    """
    Mark POIs that match saved places or bucket list.
    
    Args:
        pois: List of POIs to enrich
        saved_place_ids: IDs of saved places (from places_db)
    
    Returns:
        Enriched POI list
    """
    saved_place_ids = saved_place_ids or []
    
    for poi in pois:
        if poi.id in saved_place_ids:
            poi.is_saved_place = True
    
    return pois


# ─────────────────────────────────────────────────────────────────────────────
# Formatting for Telegram
# ─────────────────────────────────────────────────────────────────────────────

def format_suggestion_telegram(suggestion: Suggestion) -> str:
    """
    Format a suggestion for Telegram.
    Includes emoji, distance, context, and optional secondary suggestion.
    """
    primary = suggestion.primary_poi
    secondary = suggestion.secondary_poi
    
    lines = []
    
    # Header with type emoji
    if suggestion.suggestion_type == "bucket_list_match":
        lines.append("⭐ Bucket-list match nearby")
    elif suggestion.suggestion_type == "weather_friendly":
        lines.append("🌧 Rain-friendly nearby idea")
    elif suggestion.suggestion_type == "family_friendly":
        lines.append("👨‍👩‍👧‍👦 Family-friendly nearby")
    else:
        lines.append("🗺 Explore Nearby")
    
    lines.append("")
    
    # Primary POI
    distance_str = f"{primary.distance_km:.1f} km away"
    if primary.distance_km < 1.0:
        distance_str = f"{int(primary.distance_km * 1000)} m away"
    
    rating_str = ""
    if primary.rating:
        stars = "⭐" * int(primary.rating)
        rating_str = f" {stars}"
    
    lines.append(f"📍 {primary.name}{rating_str}")
    
    desc_parts = [distance_str]
    if primary.notes:
        desc_parts.append(primary.notes)
    if primary.suggested_duration_min:
        desc_parts.append(f"~{primary.suggested_duration_min} min")
    
    lines.append(f"↳ {' • '.join(desc_parts)}")
    
    # Secondary (meal suggestion)
    if secondary:
        lines.append("")
        lines.append(f"🍽 Nearby meal: {secondary.name}")
        if secondary.notes:
            lines.append(f"↳ {secondary.notes}")
    
    # Context/confidence footer
    lines.append("")
    if suggestion.suggestion_type == "bucket_list_match":
        lines.append("💡 Since this is already on your list, this is a higher-priority suggestion.")
    elif suggestion.suggestion_type == "weather_friendly":
        lines.append("💡 Better fit than outdoor walking right now.")
    else:
        lines.append(f"💡 Confidence: {suggestion.confidence_pct()}%")
    
    return "\n".join(lines)


def format_toggle_on_telegram(duration_str: str, cadence_str: str, intensity: str) -> str:
    """Format the /TripToggle On confirmation."""
    return (
        "✅ Explore Mode: ON\n"
        f"⏱ Duration: {duration_str}\n"
        f"📍 Cadence: every {cadence_str}\n"
        f"🎯 Intensity: {intensity}\n"
        "🗺 Location-aware suggestions: active\n"
        "\n"
        "You'll get nearby ideas while Explore Mode is on."
    )


def format_toggle_off_telegram() -> str:
    """Format the /TripToggle Off confirmation."""
    return (
        "🛑 Explore Mode: OFF\n"
        "\n"
        "No more nearby suggestions will be sent."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Graceful Degradation & Integration Stubs
# ─────────────────────────────────────────────────────────────────────────────

def load_saved_places_ids() -> list[str]:
    """
    Load IDs of saved places from places_db.
    Returns empty list if DB unavailable.
    Safe fallback.
    """
    try:
        from second_brain.places_db import list_all
        places = list_all(limit=1000)
        return [p.get("id") for p in places if p.get("id")]
    except Exception as e:
        print(f"⚠️ Could not load saved places (OK in degraded mode): {e}")
        return []


def load_bucket_list_ids() -> list[str]:
    """
    Load IDs of bucket-list items from places_db.
    Returns empty list if DB unavailable.
    Safe fallback.
    """
    try:
        from second_brain.places_db import list_all
        bucket = list_all(category="BucketList", limit=1000)
        return [p.get("id") for p in bucket if p.get("id")]
    except Exception as e:
        print(f"⚠️ Could not load bucket list (OK in degraded mode): {e}")
        return []


def get_weather_context() -> Optional[str]:
    """
    Fetch current weather context for suggestion filtering.
    Returns a string like "rainy", "sunny", or None if unavailable.
    Safe fallback.
    """
    try:
        # Placeholder: in Phase 2, integrate with weather API or wttr.in
        # For now, return None (no weather-aware filtering)
        return None
    except Exception:
        return None


def dummy_poi_from_place_record(record: dict) -> POI:
    """
    Convert a places_db record to a POI.
    Useful for Phase 2+ enrichment.
    """
    return POI(
        id=record.get("id", ""),
        name=record.get("name", "Unknown"),
        category=record.get("category", "Other"),
        distance_km=0.0,  # Will be computed by ranking
        rating=record.get("rating"),
        notes=record.get("notes", ""),
        maps_url=record.get("maps_url", ""),
        is_saved_place=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Utility Helpers
# ─────────────────────────────────────────────────────────────────────────────

def distance_haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Compute distance in km between two lat/lon points.
    Uses simplified Haversine formula.
    """
    import math
    R = 6371  # Earth radius in km
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


def parse_duration_spec(spec: str) -> int:
    """
    Parse duration spec into minutes.
    Supports: "2h", "30m", "eod", "trip"
    Returns minutes, or -1 for indefinite ("trip", "eod").
    """
    spec = spec.strip().lower()
    
    if spec == "trip" or spec == "eod":
        return -1  # indefinite
    
    if spec.endswith("h"):
        try:
            hours = int(spec[:-1])
            return hours * 60
        except ValueError:
            return 120
    
    if spec.endswith("m"):
        try:
            return int(spec[:-1])
        except ValueError:
            return 120
    
    return 120  # fallback


def parse_cadence_spec(spec: str) -> int:
    """
    Parse cadence spec into minutes.
    Supports: "30m", "60m", "90m"
    Returns minutes, or 60 for invalid.
    """
    spec = spec.strip().lower()
    
    if spec.endswith("m"):
        try:
            return int(spec[:-1])
        except ValueError:
            return 60
    
    return 60  # fallback


if __name__ == "__main__":
    # Quick smoke test
    print("🗺 Explore Mode Helpers — Smoke Test")
    
    # Create sample POIs
    poi1 = POI(
        id="muir-woods",
        name="Muir Woods National Monument",
        category="Park",
        distance_km=2.4,
        open_now=True,
        rating=4.7,
        notes="scenic redwood trails",
        weather_fit="outdoor",
        suggested_duration_min=90,
    )
    
    poi2 = POI(
        id="pelican-inn",
        name="Pelican Inn",
        category="Restaurant",
        distance_km=2.5,
        open_now=True,
        rating=4.2,
        notes="classic pub-style lunch nearby",
    )
    
    pois = [poi1, poi2]
    ranked = rank_nearby_pois(pois)
    print(f"✅ Ranked {len(ranked)} POIs")
    
    suggestion = select_best_suggestion(ranked)
    if suggestion:
        formatted = format_suggestion_telegram(suggestion)
        print(f"✅ Formatted suggestion:\n{formatted}")
    
    toggle_on = format_toggle_on_telegram("2 hours", "60 minutes", "medium")
    print(f"\n✅ Toggle On format:\n{toggle_on}")
    
    print("\n✅ Smoke test passed!")

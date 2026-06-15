"""
Explore Mode — POI Integration Helper

Bridges Explore Mode state with the POI provider API.
Handles location parsing, caching, and ranking of suggestions.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .poi_provider import Location, POI, SearchResult, nearby_pois, validate_provider_config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Location Handling
# ---------------------------------------------------------------------------


def parse_location_from_state(state: dict[str, Any]) -> Optional[Location]:
    """Extract and validate location from explore_state.json."""
    last_location = state.get("last_location")
    if not last_location:
        return None

    try:
        return Location(
            latitude=float(last_location.get("lat", 0)),
            longitude=float(last_location.get("lon", 0)),
            accuracy_m=last_location.get("accuracy_m"),
            source=last_location.get("source", "manual"),
        )
    except (ValueError, TypeError):
        logger.warning("Invalid location in state")
        return None


def store_location_in_state(state: dict[str, Any], location: Location) -> dict[str, Any]:
    """Update explore_state.json with a new location."""
    state["last_location"] = location.to_dict()
    return state


# ---------------------------------------------------------------------------
# POI Search with Explore Mode Context
# ---------------------------------------------------------------------------


def search_nearby_for_explore(
    location: Location,
    intensity: str = "medium",
    category_filter: Optional[str] = None,
) -> SearchResult:
    """
    Search for nearby POIs with Explore Mode context.

    Args:
        location: User's location
        intensity: "low" (5 results), "medium" (10), or "high" (20)
        category_filter: Optional category filter (e.g., "Restaurant")

    Returns:
        SearchResult with ranked POIs
    """
    # Map intensity to search parameters
    intensity_map = {
        "low": {"radius_meters": 2000, "limit": 5},
        "medium": {"radius_meters": 3000, "limit": 10},
        "high": {"radius_meters": 5000, "limit": 20},
    }
    params = intensity_map.get(intensity, intensity_map["medium"])

    result = nearby_pois(
        location=location,
        radius_meters=params["radius_meters"],
        query="restaurant cafe bar park landmark",
        category_filter=category_filter,
        limit=params["limit"],
        fallback_to_all=True,
    )

    logger.info(
        f"Explore POI search: {location} (intensity={intensity}, provider={result.provider}, "
        f"results={len(result.pois)}, duration={result.query_duration_ms:.1f}ms)"
    )

    return result


# ---------------------------------------------------------------------------
# Ranking & Deduplication
# ---------------------------------------------------------------------------


def rank_pois_for_explore(
    pois: list[POI],
    user_preferences: Optional[dict[str, Any]] = None,
    exclude_ids: Optional[set[str]] = None,
) -> list[POI]:
    """
    Rank POIs for Explore Mode based on quality signals.

    Quality factors:
    - Distance (closer is better)
    - Rating (higher is better)
    - Recency (not suggested recently)

    Args:
        pois: List of POI results
        user_preferences: Optional preferences (e.g., dietary, family-friendly)
        exclude_ids: Set of POI IDs to exclude from results

    Returns:
        Ranked list of POIs (best first)
    """
    exclude_ids = exclude_ids or set()

    # Filter out excluded POIs
    filtered = [p for p in pois if p.id not in exclude_ids]

    # Score each POI
    scored: list[tuple[float, POI]] = []
    for poi in filtered:
        score = 0.0

        # Distance: closer is better (0-1000m = 100 points, 5000m = 20 points)
        distance_score = max(0, 100 - (poi.distance_meters / 50))
        score += distance_score * 0.4

        # Rating: higher is better (0-5 stars, missing = 3 stars assumed)
        rating = poi.rating or 3.0
        score += (rating / 5.0) * 100 * 0.4

        # Availability factor: if we have open hours, prefer open places
        # (TODO: implement when opening_hours is structured)
        score += 20 * 0.2

        scored.append((score, poi))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)
    return [poi for _, poi in scored]


def filter_recent_pois(
    pois: list[POI],
    recent_suggestions: list[dict[str, Any]],
    cooldown_minutes: int = 240,
) -> list[POI]:
    """
    Remove POIs that were recently suggested to avoid repetition.

    Args:
        pois: List of POIs to filter
        recent_suggestions: Explore state's session_suggestions
        cooldown_minutes: Avoid re-suggesting same POI within N minutes

    Returns:
        Filtered list of POIs
    """
    # Extract recent POI names/titles from suggestions
    recent_names = set()
    for suggestion in recent_suggestions[-20:]:
        title = suggestion.get("title", "")
        # Extract first part before " — " or " • "
        poi_name = title.split(" — ")[0].split(" • ")[0].strip()
        if poi_name:
            recent_names.add(poi_name.lower())

    # Filter out recent suggestions
    filtered = [p for p in pois if p.name.lower() not in recent_names]
    return filtered


# ---------------------------------------------------------------------------
# Config Validation
# ---------------------------------------------------------------------------


def check_explore_config() -> dict[str, Any]:
    """
    Validate Explore Mode configuration.

    Returns:
        Dictionary with provider status and required env vars.
    """
    return validate_provider_config()


def get_missing_env_vars() -> list[str]:
    """
    Report which environment variables are needed for full functionality.

    Returns:
        List of missing env var names.
    """
    import os

    required_vars = [
        ("GOOGLE_MAPS_API_KEY", "Google Maps Places API"),
    ]

    missing = []
    for var_name, description in required_vars:
        if not os.getenv(var_name):
            missing.append(f"{var_name} ({description})")

    return missing

"""
Nearby POI Lookup — Provider Abstraction & API Scaffolding

Implements a clean provider interface for nearby place discovery:
- GoogleMapsProvider (production-ready)
- OpenStreetMapProvider (fallback/open-source)
- LocalDBProvider (graceful fallback when no API available)

Gracefully handles missing API keys, network errors, and invalid location input.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass
class Location:
    """A geographic coordinate with optional metadata."""
    latitude: float
    longitude: float
    accuracy_m: Optional[int] = None  # accuracy in meters
    source: str = "manual"  # "gps", "device", "manual", "ip_geoip", etc.

    def __str__(self) -> str:
        return f"({self.latitude:.4f}, {self.longitude:.4f})"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Location:
        return cls(
            latitude=d["latitude"],
            longitude=d["longitude"],
            accuracy_m=d.get("accuracy_m"),
            source=d.get("source", "manual"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "accuracy_m": self.accuracy_m,
            "source": self.source,
        }


@dataclass
class POI:
    """A Point of Interest returned by a provider."""
    id: str
    name: str
    category: str  # "Restaurant", "Park", "Landmark", etc.
    latitude: float
    longitude: float
    distance_meters: float
    rating: Optional[float] = None  # 0-5 scale
    user_ratings_count: Optional[int] = None
    address: str = ""
    phone: str = ""
    website: str = ""
    opening_hours: Optional[dict[str, Any]] = None  # provider-specific format
    photos: list[str] = None  # URLs
    provider: str = "unknown"
    raw_data: Optional[dict[str, Any]] = None  # full response from API

    def __post_init__(self) -> None:
        if self.photos is None:
            self.photos = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "distance_meters": self.distance_meters,
            "rating": self.rating,
            "user_ratings_count": self.user_ratings_count,
            "address": self.address,
            "phone": self.phone,
            "website": self.website,
            "opening_hours": self.opening_hours,
            "photos": self.photos,
            "provider": self.provider,
        }


@dataclass
class SearchResult:
    """Result of a nearby POI search."""
    pois: list[POI]
    location: Location
    provider: str
    query_duration_ms: float
    error: Optional[str] = None  # set if search failed gracefully
    api_key_required: bool = False  # set if missing API key prevented full search

    def is_fallback(self) -> bool:
        return self.api_key_required or self.error is not None


# ---------------------------------------------------------------------------
# Provider Interface
# ---------------------------------------------------------------------------


class POIProvider(ABC):
    """Abstract base class for POI providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name, e.g. 'google_maps', 'osm', 'local_db'."""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """True if provider is configured and ready."""
        pass

    @abstractmethod
    def nearby(
        self,
        location: Location,
        radius_meters: int = 5000,
        query: Optional[str] = None,
        category_filter: Optional[str] = None,
        limit: int = 10,
    ) -> SearchResult:
        """Search for nearby POIs."""
        pass


# ---------------------------------------------------------------------------
# Google Maps Provider
# ---------------------------------------------------------------------------


class GoogleMapsProvider(POIProvider):
    """Google Maps Places API for nearby POI lookup."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.getenv("GOOGLE_MAPS_API_KEY", "").strip()

    @property
    def name(self) -> str:
        return "google_maps"

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    def nearby(
        self,
        location: Location,
        radius_meters: int = 5000,
        query: Optional[str] = None,
        category_filter: Optional[str] = None,
        limit: int = 10,
    ) -> SearchResult:
        """Query Google Maps Places API for nearby POIs."""
        import time
        start_time = time.time()

        if not self.is_available:
            logger.warning("Google Maps API key not configured")
            return SearchResult(
                pois=[],
                location=location,
                provider=self.name,
                query_duration_ms=0,
                error="API key not configured",
                api_key_required=True,
            )

        try:
            import googlemaps
            client = googlemaps.Client(key=self.api_key)

            # Build search query
            search_query = query or category_filter or "restaurants"

            # Perform nearby search
            result = client.places_nearby(
                location=(location.latitude, location.longitude),
                radius=radius_meters,
                keyword=search_query,
                language="en",
            )

            pois = []
            for place in result.get("results", [])[:limit]:
                poi = self._parse_google_place(place, location)
                pois.append(poi)

            duration_ms = (time.time() - start_time) * 1000
            return SearchResult(
                pois=pois,
                location=location,
                provider=self.name,
                query_duration_ms=duration_ms,
            )

        except ImportError:
            logger.warning("googlemaps library not installed")
            return SearchResult(
                pois=[],
                location=location,
                provider=self.name,
                query_duration_ms=(time.time() - start_time) * 1000,
                error="googlemaps library not installed",
            )
        except Exception as e:
            logger.error(f"Google Maps API error: {e}")
            duration_ms = (time.time() - start_time) * 1000
            return SearchResult(
                pois=[],
                location=location,
                provider=self.name,
                query_duration_ms=duration_ms,
                error=str(e),
            )

    def _parse_google_place(self, place: dict[str, Any], user_location: Location) -> POI:
        """Convert a Google Maps place result to POI."""
        from math import radians, cos, sin, asin, sqrt

        def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
            """Calculate distance in meters between two lat/lon points."""
            lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
            dlon = lon2 - lon1
            dlat = lat2 - lat1
            a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
            c = 2 * asin(sqrt(a))
            km = 6371 * c
            return km * 1000

        lat = place.get("geometry", {}).get("location", {}).get("lat", user_location.latitude)
        lon = place.get("geometry", {}).get("location", {}).get("lng", user_location.longitude)
        distance = haversine(user_location.latitude, user_location.longitude, lat, lon)

        # Map Google place type to our category
        place_types = place.get("types", [])
        category = self._google_type_to_category(place_types)

        return POI(
            id=place.get("place_id", ""),
            name=place.get("name", "Unknown"),
            category=category,
            latitude=lat,
            longitude=lon,
            distance_meters=distance,
            rating=place.get("rating"),
            user_ratings_count=place.get("user_ratings_total"),
            address=place.get("vicinity", ""),
            opening_hours=place.get("opening_hours"),
            provider=self.name,
            raw_data=place,
        )

    @staticmethod
    def _google_type_to_category(types: list[str]) -> str:
        """Map Google place types to our categories."""
        type_map = {
            "restaurant": "Restaurant",
            "cafe": "Cafe",
            "bar": "Bar",
            "hotel": "Hotel",
            "lodging": "Hotel",
            "grocery_or_supermarket": "Market",
            "landmark": "Landmark",
            "park": "Park",
            "shopping_mall": "Shop",
            "clothing_store": "Shop",
            "museum": "Landmark",
            "art_gallery": "Landmark",
        }
        for t in types:
            if t in type_map:
                return type_map[t]
        return "Other"


# ---------------------------------------------------------------------------
# OpenStreetMap Provider (Nominatim + Overpass)
# ---------------------------------------------------------------------------


class OpenStreetMapProvider(POIProvider):
    """OpenStreetMap POI lookup via Nominatim + simple local matching."""

    def __init__(self) -> None:
        pass

    @property
    def name(self) -> str:
        return "osm"

    @property
    def is_available(self) -> bool:
        # OSM is always "available" in principle, but we keep this for consistency
        return True

    def nearby(
        self,
        location: Location,
        radius_meters: int = 5000,
        query: Optional[str] = None,
        category_filter: Optional[str] = None,
        limit: int = 10,
    ) -> SearchResult:
        """
        Search for nearby POIs using OSM data.
        For now, this is a stub that returns empty results gracefully.
        In future, can integrate with Overpass API or local OSM tiles.
        """
        import time
        start_time = time.time()

        # TODO: Implement Overpass API or local tile-based lookup
        logger.info(f"OSM provider called for {location} within {radius_meters}m")

        return SearchResult(
            pois=[],
            location=location,
            provider=self.name,
            query_duration_ms=(time.time() - start_time) * 1000,
            error="OSM provider not yet implemented; use Google Maps or Local DB",
        )


# ---------------------------------------------------------------------------
# Local Database Fallback Provider
# ---------------------------------------------------------------------------


class LocalDBProvider(POIProvider):
    """Fallback provider using saved places from places_db."""

    def __init__(self) -> None:
        self._places_module: Optional[Any] = None

    def _load_places_module(self) -> bool:
        """Lazy-load places_db module."""
        if self._places_module is not None:
            return True
        try:
            from . import places_db
            self._places_module = places_db
            return True
        except ImportError:
            logger.warning("places_db module not available")
            return False

    @property
    def name(self) -> str:
        return "local_db"

    @property
    def is_available(self) -> bool:
        return self._load_places_module()

    def nearby(
        self,
        location: Location,
        radius_meters: int = 5000,
        query: Optional[str] = None,
        category_filter: Optional[str] = None,
        limit: int = 10,
    ) -> SearchResult:
        """Search saved places for ones near the given location."""
        import time
        from math import radians, cos, sin, asin, sqrt

        start_time = time.time()

        if not self._load_places_module():
            return SearchResult(
                pois=[],
                location=location,
                provider=self.name,
                query_duration_ms=(time.time() - start_time) * 1000,
                error="places_db not available",
            )

        def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
            lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
            dlon = lon2 - lon1
            dlat = lat2 - lat1
            a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
            c = 2 * asin(sqrt(a))
            return 6371 * c * 1000  # meters

        try:
            # Get all saved places
            all_places = self._places_module.list_all(limit=1000)

            pois = []
            for place in all_places:
                # For now, we use city name as rough location
                # A real implementation would geocode saved places
                # and check if they're within radius_meters
                poi = POI(
                    id=place.get("id", ""),
                    name=place.get("name", ""),
                    category=place.get("category", "Other"),
                    latitude=0.0,  # TODO: geocode saved places
                    longitude=0.0,
                    distance_meters=0,
                    address=f"{place.get('city', '')}, {place.get('country', '')}".strip(", "),
                    rating=place.get("rating"),
                    provider=self.name,
                )
                pois.append(poi)

            # Filter by category if provided
            if category_filter:
                pois = [p for p in pois if p.category.lower() == category_filter.lower()]

            duration_ms = (time.time() - start_time) * 1000
            return SearchResult(
                pois=pois[:limit],
                location=location,
                provider=self.name,
                query_duration_ms=duration_ms,
                error="Local DB provides place names only; geolocation pending",
            )

        except Exception as e:
            logger.error(f"LocalDB provider error: {e}")
            duration_ms = (time.time() - start_time) * 1000
            return SearchResult(
                pois=[],
                location=location,
                provider=self.name,
                query_duration_ms=duration_ms,
                error=str(e),
            )


# ---------------------------------------------------------------------------
# Provider Registry & Factory
# ---------------------------------------------------------------------------


class POIProviderRegistry:
    """Registry and factory for POI providers."""

    def __init__(self) -> None:
        self._providers: dict[str, POIProvider] = {}

    def register(self, provider: POIProvider) -> None:
        """Register a provider by name."""
        self._providers[provider.name] = provider

    def get(self, name: str) -> Optional[POIProvider]:
        """Retrieve a provider by name."""
        return self._providers.get(name)

    def get_available(self) -> list[POIProvider]:
        """Return list of available (configured) providers."""
        return [p for p in self._providers.values() if p.is_available]

    def get_primary_available(self) -> Optional[POIProvider]:
        """Return first available provider in priority order."""
        # Priority: google_maps > osm > local_db
        priority = ["google_maps", "osm", "local_db"]
        for name in priority:
            provider = self.get(name)
            if provider and provider.is_available:
                return provider
        return None


# Global registry
_registry: Optional[POIProviderRegistry] = None


def get_registry() -> POIProviderRegistry:
    """Get or initialize the global provider registry."""
    global _registry
    if _registry is None:
        _registry = POIProviderRegistry()
        _registry.register(GoogleMapsProvider())
        _registry.register(OpenStreetMapProvider())
        _registry.register(LocalDBProvider())
    return _registry


# ---------------------------------------------------------------------------
# Convenience API
# ---------------------------------------------------------------------------


def nearby_pois(
    location: Location,
    radius_meters: int = 5000,
    query: Optional[str] = None,
    category_filter: Optional[str] = None,
    limit: int = 10,
    fallback_to_all: bool = True,
) -> SearchResult:
    """
    Search for nearby POIs using the best available provider.

    Args:
        location: Geographic location (lat/lon)
        radius_meters: Search radius in meters
        query: Text query (e.g. "restaurant", "coffee")
        category_filter: Filter by category (e.g. "Restaurant")
        limit: Max results to return
        fallback_to_all: If primary provider fails, try LocalDB as fallback

    Returns:
        SearchResult with POIs or error info
    """
    registry = get_registry()
    provider = registry.get_primary_available()

    if provider is None:
        logger.warning("No POI providers available")
        return SearchResult(
            pois=[],
            location=location,
            provider="none",
            query_duration_ms=0,
            error="No POI providers configured",
        )

    result = provider.nearby(
        location,
        radius_meters=radius_meters,
        query=query,
        category_filter=category_filter,
        limit=limit,
    )

    # If primary provider failed and fallback is enabled, try local DB
    if result.is_fallback() and fallback_to_all and provider.name != "local_db":
        logger.info(f"Primary provider ({provider.name}) failed; trying local DB fallback")
        local_provider = registry.get("local_db")
        if local_provider and local_provider.is_available:
            result = local_provider.nearby(
                location,
                radius_meters=radius_meters,
                query=query,
                category_filter=category_filter,
                limit=limit,
            )

    return result


# ---------------------------------------------------------------------------
# Testing & Validation
# ---------------------------------------------------------------------------


def validate_provider_config() -> dict[str, Any]:
    """Check which providers are available and report missing config."""
    registry = get_registry()
    status = {
        "google_maps": {
            "available": registry.get("google_maps").is_available,
            "config_key": "GOOGLE_MAPS_API_KEY",
            "status": "configured" if registry.get("google_maps").is_available else "missing API key",
        },
        "osm": {
            "available": registry.get("osm").is_available,
            "status": "available (not yet implemented)",
        },
        "local_db": {
            "available": registry.get("local_db").is_available,
            "status": "available" if registry.get("local_db").is_available else "places_db not found",
        },
        "primary": registry.get_primary_available().name if registry.get_primary_available() else "none",
    }
    return status

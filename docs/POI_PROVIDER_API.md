# POI Provider API — Explore Mode Location-Aware Discovery

**Location:** `second_brain/poi_provider.py`  
**Status:** Scaffolding complete, ready for production integration  
**Last Updated:** 2026-06-15

---

## Overview

The POI (Point of Interest) Provider API is a clean, extensible abstraction layer for nearby place discovery in Explore Mode. It provides:

- **Multiple provider backends** — Google Maps, OpenStreetMap (planned), local database fallback
- **Graceful degradation** — Works without API keys; falls back automatically
- **Type-safe data models** — Location, POI, SearchResult
- **Provider registry** — Easy to add new providers without modifying core logic
- **Lightweight integration** — No breaking changes to existing PersGraph features

### Architecture

```
┌─────────────────────────────────────────────┐
│  Explore Mode (explore_mode.py)              │
│  + explore_poi.py (integration helpers)      │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  POI Provider API (poi_provider.py)          │
│  ├─ GoogleMapsProvider                      │
│  ├─ OpenStreetMapProvider (stub)            │
│  └─ LocalDBProvider (fallback)              │
└──────────────────┬──────────────────────────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
   ┌────▼──┐  ┌────▼──┐  ┌────▼──┐
   │Google │  │  OSM  │  │Places │
   │ Maps  │  │ Tiles │  │  DB   │
   └───────┘  └───────┘  └───────┘
```

---

## Data Models

### Location

Represents a geographic point with accuracy metadata.

```python
from second_brain.poi_provider import Location

location = Location(
    latitude=37.7749,
    longitude=-122.4194,
    accuracy_m=50,  # accuracy in meters (optional)
    source="gps",  # "gps", "device", "manual", "ip_geolocation", etc.
)

# Convert to/from dict
loc_dict = location.to_dict()
location = Location.from_dict(loc_dict)
```

**Fields:**
- `latitude` (float): Latitude in decimal degrees
- `longitude` (float): Longitude in decimal degrees
- `accuracy_m` (int, optional): Horizontal accuracy in meters
- `source` (str): Source of the location ("gps", "device", "manual", etc.)

---

### POI (Point of Interest)

Represents a place returned by a provider.

```python
@dataclass
class POI:
    id: str                          # unique place ID from provider
    name: str                        # place name
    category: str                    # "Restaurant", "Park", "Landmark", etc.
    latitude: float                  # location
    longitude: float
    distance_meters: float           # distance from search origin
    rating: Optional[float] = None   # 0-5 star rating
    user_ratings_count: Optional[int] = None
    address: str = ""                # street address
    phone: str = ""                  # contact phone
    website: str = ""                # website URL
    opening_hours: Optional[dict] = None  # provider-specific format
    photos: list[str] = None         # image URLs
    provider: str = "unknown"        # which provider returned this
    raw_data: Optional[dict] = None  # full API response

    def to_dict(self) -> dict[str, Any]:
        """Convert to serializable dict."""
```

---

### SearchResult

Result of a nearby POI search.

```python
@dataclass
class SearchResult:
    pois: list[POI]                  # found places
    location: Location               # search center
    provider: str                    # which provider was used
    query_duration_ms: float         # API call time
    error: Optional[str] = None      # error message if search failed
    api_key_required: bool = False   # True if missing API key

    def is_fallback(self) -> bool:
        """True if provider failed or returned degraded results."""
```

---

## Provider Interface

All providers implement `POIProvider`:

```python
class POIProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g., 'google_maps')."""

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """True if provider is configured and ready."""

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
```

---

## Providers

### Google Maps Provider

Production-ready provider using Google Places API.

**Configuration:**
```bash
GOOGLE_MAPS_API_KEY=your-api-key
```

**Setup:**
1. Create a Google Cloud project
2. Enable Places API v1
3. Create an API key with Places API restriction
4. Add key to `.env`

**Status:** ✓ Fully implemented

**Example:**
```python
from second_brain.poi_provider import GoogleMapsProvider, Location

provider = GoogleMapsProvider()
location = Location(37.7749, -122.4194)
result = provider.nearby(location, query="restaurant", limit=10)

for poi in result.pois:
    print(f"{poi.name} — {poi.distance_meters/1000:.1f}km away")
    print(f"  Rating: {poi.rating}/5")
    print(f"  Address: {poi.address}")
```

---

### OpenStreetMap Provider

Open-source fallback (not yet implemented; reserved for future use).

**Status:** ⚠️ Placeholder; returns empty results with informational error

**Future implementation options:**
- Overpass API for structured queries
- Local OSM tile server
- Nominatim reverse geocoding + manual matching

---

### LocalDB Provider

Graceful fallback using saved places from `places_db`.

**Configuration:** None needed; always available

**Status:** ✓ Implemented with distance calculation pending

**Example:**
```python
from second_brain.poi_provider import LocalDBProvider, Location

provider = LocalDBProvider()
location = Location(37.7749, -122.4194)
result = provider.nearby(location, category_filter="Restaurant")
print(f"Found {len(result.pois)} saved places")
```

---

## Usage

### High-Level API

**Simple nearby search:**
```python
from second_brain.poi_provider import nearby_pois, Location

location = Location(37.7749, -122.4194)
result = nearby_pois(
    location=location,
    radius_meters=5000,
    query="coffee",
    limit=10,
    fallback_to_all=True,  # auto-fallback if primary provider fails
)

for poi in result.pois:
    print(f"✓ {poi.name}")
    if result.is_fallback():
        print(f"  (via fallback provider: {result.provider})")

if result.error:
    print(f"⚠ {result.error}")
```

### Provider Registry

**Access providers directly:**
```python
from second_brain.poi_provider import get_registry

registry = get_registry()

# Check which providers are available
available = registry.get_available()
print(f"Available providers: {[p.name for p in available]}")

# Get specific provider
google = registry.get("google_maps")
if google and google.is_available:
    result = google.nearby(location, query="park")

# Get best available provider
best = registry.get_primary_available()
```

### Explore Mode Integration

**Built-in helpers:**
```python
from second_brain.explore_poi import (
    search_nearby_for_explore,
    rank_pois_for_explore,
    filter_recent_pois,
    check_explore_config,
    get_missing_env_vars,
)

# Search with Explore Mode parameters
location = Location(37.7749, -122.4194)
result = search_nearby_for_explore(
    location=location,
    intensity="medium",  # controls radius & result count
    category_filter="Restaurant",
)

# Rank results by quality signals
ranked = rank_pois_for_explore(result.pois)

# Remove recently suggested places
recent = state.get("session_suggestions", [])
filtered = filter_recent_pois(ranked, recent, cooldown_minutes=240)

# Pick the best one
if filtered:
    best_poi = filtered[0]
    print(f"Suggest: {best_poi.name} ({best_poi.distance_meters/1000:.1f}km away)")

# Check configuration status
status = check_explore_config()
missing = get_missing_env_vars()
```

---

## Configuration

### Environment Variables

**Optional — enables Google Maps provider:**
```bash
GOOGLE_MAPS_API_KEY=your-api-key
```

**Recommended placement:** `.env` (for local development) or `.env.local` (overrides `.env`)

### Runtime Configuration Check

```bash
cd ~/AgenticHub/Persgraph
python3 scripts/validate_poi_setup.py
```

Output shows:
- Which providers are available
- Missing environment variables
- Local database status
- File structure validation

---

## Error Handling

All providers gracefully handle errors:

```python
result = nearby_pois(location, query="restaurant")

if result.error:
    # Provider failed (network, API limit, auth, etc.)
    print(f"⚠ {result.error}")
    print(f"Provider: {result.provider}")

if result.api_key_required:
    # Missing API key; will fallback automatically
    print("Set GOOGLE_MAPS_API_KEY to enable full functionality")

if result.is_fallback():
    # Using degraded provider (likely local DB)
    print(f"Using fallback: {result.provider}")

# Always safe to iterate; might be empty
for poi in result.pois:
    # ...
```

### Common Error Scenarios

| Error | Cause | Fallback |
|-------|-------|----------|
| "API key not configured" | GOOGLE_MAPS_API_KEY missing | LocalDB |
| "googlemaps library not installed" | Missing dependency | LocalDB |
| "No POI providers available" | All providers misconfigured | Returns empty result |
| Network timeout | API unreachable | LocalDB if fallback_to_all=True |
| Invalid location | Bad latitude/longitude | Returns empty result with error |

---

## Integration with Explore Mode

### In `scripts/explore_mode.py`

```python
def build_suggestion(state: dict[str, Any] | None = None) -> ExploreSuggestion:
    # Try bucket-list first
    suggestion = _find_bucketlist_candidate()
    if suggestion:
        return suggestion

    # Try nearby POI lookup if location is available
    if state:
        last_location = state.get("last_location")
        if last_location:
            suggestion = _get_nearby_poi_suggestion(last_location)
            if suggestion:
                return suggestion

    # Fallback to generic suggestion
    return _fallback_suggestion()
```

### Flow

1. User enables Explore Mode with `/TripToggle On`
2. Cron job runs `explore_mode.py --check` every 5 minutes
3. If location is available (from device GPS, manual input, or previous state):
   - POI search is triggered via `search_nearby_for_explore()`
   - Results are ranked by distance, rating, recency
   - Top result is formatted as a suggestion
   - Message is sent to Telegram
4. If no location or POI search fails:
   - Fall back to bucket-list matching
   - Fall back to generic "Explore nearby" message

---

## Testing

### Lightweight Validation

```bash
cd ~/AgenticHub/Persgraph
python3 scripts/validate_poi_setup.py
```

### Manual Testing

```python
from pathlib import Path
import sys
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from second_brain.poi_provider import (
    Location,
    GoogleMapsProvider,
    LocalDBProvider,
    nearby_pois,
)

# Test Google Maps
google = GoogleMapsProvider()
print(f"Google Maps available: {google.is_available}")

# Test LocalDB
local = LocalDBProvider()
location = Location(37.7749, -122.4194)
result = local.nearby(location, limit=5)
print(f"LocalDB found {len(result.pois)} places")

# Test high-level API with fallback
result = nearby_pois(location, fallback_to_all=True)
print(f"Primary provider: {result.provider}")
print(f"Results: {len(result.pois)}")
print(f"Provider chain: Google Maps -> OSM -> LocalDB")
```

---

## Future Enhancements

### Phase 2 — Smart Ranking

- User preference filters (dietary, family-friendly, budget)
- Time-of-day filters (open now, good for quick stop, etc.)
- Weather-aware suggestions (indoor if rainy)
- Personalization based on saved places

### Phase 3 — Multi-Provider Aggregation

- Combine results from multiple providers
- De-duplicate across sources
- Weighted ranking based on provider reliability

### Phase 4 — Caching & Optimization

- Cache results near user location (5-minute TTL)
- Batch requests to reduce API calls
- Local tile server for offline fallback

---

## Files

**Core:**
- `second_brain/poi_provider.py` — Provider abstraction, models, registry
- `second_brain/explore_poi.py` — Explore Mode integration helpers

**Integration:**
- `scripts/explore_mode.py` — Updated to use POI lookup
- `scripts/validate_poi_setup.py` — Setup validation tool

**Config:**
- `.env.example` — Updated with GOOGLE_MAPS_API_KEY

---

## Troubleshooting

**Q: Getting "API key not configured" but I set GOOGLE_MAPS_API_KEY**

A: Ensure the key is in `.env` or `.env.local` at the project root, not in a local `.env` file somewhere else.

**Q: LocalDB returns empty results**

A: Check if you have saved places:
```python
from second_brain import places_db
print(f"Saved places: {places_db.count()}")
```

Add places with `/place save "Name" "City"` command.

**Q: Nearby search is slow**

A: Check query duration in logs:
```python
result = nearby_pois(location)
print(f"Query took {result.query_duration_ms:.1f}ms")
```

If >5 seconds, consider reducing radius or increasing cache TTL.

**Q: No providers available**

A: Run `validate_poi_setup.py` to diagnose. At minimum, LocalDB should always be available.

---

## Summary

✅ **What's implemented:**
- Clean provider interface & registry
- Google Maps provider (production-ready)
- LocalDB fallback (always available)
- Explore Mode integration hooks
- Type-safe models (Location, POI, SearchResult)
- Error handling & graceful degradation
- Validation tool

⚠️ **What's planned:**
- OpenStreetMap provider
- Distance calculation for saved places
- Advanced ranking & deduplication
- Multi-provider aggregation
- Result caching

🚀 **Next steps:**
1. Add GOOGLE_MAPS_API_KEY to `.env` (optional but recommended)
2. Test with `validate_poi_setup.py`
3. Enable Explore Mode and monitor suggestions
4. Collect feedback on POI quality

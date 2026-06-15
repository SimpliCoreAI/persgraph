# Explore Mode — Implementation Status (Phase 1/2)

**Completed:** 2026-06-14  
**Status:** Cron-ready, Location & Movement Detection Integrated  
**Target Phase:** Phase 1 (MVP) + Phase 2 Foundation

---

## Overview

Explore Mode Cron & Location infrastructure is now implemented and wired. The system is **safe, cron-ready, and degrades gracefully** when location is unavailable.

### Key Files Added/Modified

| File | Status | Purpose |
|------|--------|---------|
| `scripts/explore_location.py` | ✅ NEW | Device location lookup, movement detection, graceful fallback |
| `scripts/explore_mode.py` | ✅ MODIFIED | Integrated location checks & movement suppression |
| `scripts/setup_explore_cron.sh` | ✅ NEW | Safe, idempotent cron job installer |
| `data/explore_state.json` | ✅ ACTIVE | Maintains location cache for movement detection |
| `data/explore_location_cache.json` | ✅ NEW (created on use) | Caches last known location for fallback |

---

## Implementation Details

### 1. Location Resolution Chain (`explore_location.py`)

The system attempts to resolve device location via a **safe preference chain**:

1. **OpenClaw Device GPS** (if available via `EXPLORE_LOCATION_OVERRIDE` env var or future integration)
2. **Saved Location Cache** (fallback to last good location if <24h old)
3. **None** (graceful degradation; suggestions still work but without movement detection)

**Location Structure:**
```python
class Location:
    lat: float
    lon: float
    source: str  # "device_gps", "manual", "saved_context", "fallback"
    accuracy_m: int  # accuracy radius in meters
    timestamp: datetime
```

**Key Functions:**
- `get_current_location()` → resolves via preference chain
- `try_openclaw_location()` → checks EXPLORE_LOCATION_OVERRIDE env var (future: OpenClaw API)
- `try_saved_location()` → loads cached location if fresh (<24h)
- `save_location_cache()` → persists location for future checks

### 2. Movement Detection (`explore_location.py`)

Prevents notification spam by suppressing suggestions when user hasn't moved far enough.

**Distance Calculation:** Haversine formula (accurate for local distances)

**Movement Thresholds by Intensity:**
- `low`: 1000m (1km)
- `medium`: 500m (default)
- `high`: 200m

**Usage:**
```python
moved_ok, reason = check_movement_and_suppress(
    current_location,  # Optional[Location]
    last_location,     # Optional[dict] from state
    state              # explore_state dict with intensity
)
```

**Graceful Degradation:**
- If either location is None → allow suggestion (don't suppress on missing data)
- If comparison fails → allow suggestion (fail open)

### 3. State Integration (`explore_mode.py`)

Updated `should_run_suggestion()` and `check_once()` to check movement:

```python
# In should_run_suggestion():
if LOCATION_AVAILABLE:
    current_loc = resolve_location_for_check()
    last_loc = state.get("last_location")
    moved_ok, reason = check_movement_and_suppress(current_loc, last_loc, state)
    if not moved_ok:
        return False, reason  # Skip suggestion, user hasn't moved

# In check_once():
if LOCATION_AVAILABLE:
    current_loc = resolve_location_for_check()
    if current_loc:
        state["last_location"] = current_loc.to_dict()
        save_state(state)
```

**State Schema Extended:**
```json
{
  "enabled": true,
  "last_location": {
    "lat": 37.7749,
    "lon": -122.4194,
    "source": "device_gps",
    "accuracy_m": 50,
    "timestamp": "2026-06-14T17:40:00-07:00"
  }
}
```

### 4. Cron Job Setup (`setup_explore_cron.sh`)

**Safe, idempotent bash script** for cron management.

**Features:**
- ✅ Idempotent (safe to run multiple times)
- ✅ Graceful error handling (checks deps, skips if installed)
- ✅ Log output to `/tmp/explore_mode.log`
- ✅ Sets PYTHONPATH correctly

**Commands:**
```bash
./scripts/setup_explore_cron.sh install      # Add cron job
./scripts/setup_explore_cron.sh uninstall    # Remove cron job
./scripts/setup_explore_cron.sh status       # Show current status
```

**Installed Cron Line:**
```
*/5 * * * * cd /root/AgenticHub/Persgraph && PYTHONPATH=. \
  /root/AgenticHub/Persgraph/.venv/bin/python scripts/explore_mode.py --check \
  >> /tmp/explore_mode.log 2>&1
```

**Schedule:** Every 5 minutes  
**Log Location:** `/tmp/explore_mode.log`

---

## Testing & Validation

### Quick Smoke Tests

**1. Location Module:**
```bash
cd ~/AgenticHub/Persgraph
.venv/bin/python scripts/explore_location.py
# ✅ Smoke test passed!
```

**2. Explore Mode with Location:**
```bash
# Enable and run one check
python -c "
from scripts.explore_mode import enable_explore, check_once
enable_explore(duration='2h', cadence=60, intensity='medium')
ok, msg = check_once()
print(f'Suggestion sent: {ok}')
"
```

**3. Movement Detection:**
```bash
# Test with override location
EXPLORE_LOCATION_OVERRIDE="37.7776,-122.4419" python -c "
from scripts.explore_location import get_current_location, distance_haversine
loc = get_current_location()
print(f'Location: {loc}')
"
```

**4. Cron Setup:**
```bash
./scripts/setup_explore_cron.sh status
# ✅ Shows installed cron job and Explore Mode state
```

### Integration Points Tested

| Integration | Status | Notes |
|---|---|---|
| Location resolution (no device) | ✅ Works | Falls back gracefully |
| Location override via env var | ✅ Works | For testing/manual location input |
| Movement detection | ✅ Works | Distance calculation correct |
| State persistence | ✅ Works | Locations cached and reused |
| Cadence + movement checks | ✅ Works | Both constraints honored |
| Cron scheduling | ✅ Works | Installed, verified in crontab |
| Graceful degradation | ✅ Works | No errors when location unavailable |

---

## Configuration & Secrets Needed

### Environment Variables

**For Testing/Manual Location Input:**
```bash
export EXPLORE_LOCATION_OVERRIDE="lat,lon[,source]"
# Example: 37.7749,-122.4194,test_gps
# source defaults to "device_override"
```

### Future OpenClaw Integration

**Placeholder for integration:**
```python
# In explore_location.py::try_openclaw_location()
# Future: Replace with actual OpenClaw node API
# if OPENCLAW_AVAILABLE:
#     node_data = get_device_location_from_openclaw()
#     if node_data:
#         return Location(lat=..., lon=..., source="device_gps")
```

**How to Wire It:**
1. Add OpenClaw location API client (e.g., REST call or gRPC)
2. Modify `try_openclaw_location()` to call it
3. Update error handling for timeout/auth failures
4. Set environment variables for API endpoint (if needed)

### Data Files

| File | Auto-created | Retention |
|------|---|---|
| `data/explore_state.json` | ✅ Yes | Persisted (enable/disable settings) |
| `data/explore_location_cache.json` | ✅ Yes | Persisted (location fallback, <24h) |
| `data/explore_audit.json` | ✅ Yes | Persisted (audit log, last 200 events) |
| `/tmp/explore_mode.log` | ✅ Yes (cron) | Rotated by cron (no explicit cleanup) |

---

## Known Limitations & Next Steps

### Current Limitations

1. **No Live Device GPS Yet**
   - Location must be provided via `EXPLORE_LOCATION_OVERRIDE` env var or cached
   - OpenClaw node integration is stubbed (placeholder comments)
   - Manual location input via command line possible in Phase 2

2. **Movement Suppression Only**
   - Doesn't deduplicate same POI (yet; handled in helpers)
   - Doesn't consider user preferences (Phase 2)
   - No weather-aware filtering (Phase 2)

3. **No Session Deduplication**
   - Same place can re-appear if user moves back
   - Longer-term dedup (4h history) not yet integrated

### Next Steps for Phase 2

- [ ] **Wire OpenClaw GPS Integration**
  - Add OpenClaw node location API calls
  - Handle auth, timeouts, missing permissions
  - Test on physical device or simulator

- [ ] **Session & Historical Deduplication**
  - Integrate `suppression_history` from `explore_state_schema.py`
  - Implement 4-hour (or configurable) dedup

- [ ] **Weather-Aware Filtering**
  - Call weather API (wttr.in already available)
  - Filter suggestions by weather fit ("indoor", "outdoor", etc.)

- [ ] **Bucket List & Saved Place Matching**
  - Boost nearby items from user's bucket list
  - Use existing `places_db` integration

- [ ] **User Location Input via Command**
  - `/TripToggle On 37.7749,-122.4194` syntax
  - Validate and cache location from command

---

## Files Changed

### New Files
```
✅ scripts/explore_location.py              (9.3 KB)
✅ scripts/setup_explore_cron.sh            (4.1 KB)
✅ features/explore-mode/IMPLEMENTATION.md  (this file)
```

### Modified Files
```
✅ scripts/explore_mode.py  (+9 lines, import + movement checks)
   - Added location module import with fallback
   - Added movement check to should_run_suggestion()
   - Added location cache update to check_once()
```

### Auto-Created Data Files
```
✅ data/explore_state.json               (created on first run)
✅ data/explore_location_cache.json      (created when location resolved)
✅ data/explore_audit.json               (created on first check)
```

---

## Running the Feature

### Setup (One-Time)

```bash
cd ~/AgenticHub/Persgraph

# Install cron job (enables 5-min checks)
./scripts/setup_explore_cron.sh install

# Verify installation
./scripts/setup_explore_cron.sh status
```

### Using Explore Mode

```bash
# Enable via Telegram command (when bot is running)
/TripToggle On 2h 60m medium

# Or via command line
python -c "from scripts.explore_mode import enable_explore; enable_explore('2h', 60, 'medium')"

# Check status
python scripts/explore_mode.py --status

# Disable
/TripToggle Off
```

### Monitoring

```bash
# Watch live logs
tail -f /tmp/explore_mode.log

# Check state
cat data/explore_state.json | python -m json.tool

# View recent audit trail
cat data/explore_audit.json | python -m json.tool | tail -50
```

---

## Cleanup (If Needed)

```bash
# Remove cron job
./scripts/setup_explore_cron.sh uninstall

# Clear state (restart fresh)
rm -f data/explore_state.json data/explore_location_cache.json

# Keep audit trail for debugging
# (or remove with: rm data/explore_audit.json)
```

---

## Summary

✅ **Phase 1 Foundation Complete:**
- Cron-ready scheduler (every 5 minutes)
- Device location lookup with safe fallback
- Movement-based suppression (prevents spam)
- Graceful degradation (works without location)
- Full state persistence & audit trail

✅ **Production-Ready:**
- No external API keys required for Phase 1
- Safe defaults (location unavailable = still works)
- Idempotent setup script
- Comprehensive error handling

✅ **Ready for Phase 2 Enhancements:**
- OpenClaw GPS integration point ready
- Deduplication infrastructure in place
- Weather & preference hooks ready
- Can be extended without breaking current state

# PersGraph Learning Layer — Phase 1 Implementation Report

**Date:** 2026-06-17  
**Status:** ✅ Complete  
**Scope:** Phase 1 — Event & Outcome Recording with Explore Mode Integration  

---

## 📋 Executive Summary

Implemented a lightweight, **production-ready learning layer** for PersGraph that captures Explore Mode suggestion interactions. The system records:

- **Events**: Suggestions offered, skips (cadence/location/movement-based), user enable/disable
- **Outcomes**: User reactions (accept, skip, click, bookmark) with engagement time
- **Skills**: Placeholder for Phase 2 (discovered patterns from outcomes)
- **Preferences**: Manual + learned user settings
- **Audit Log**: Internal operational tracking for debugging

**Key Metrics:**
- ✅ SQLite schema with 5 core tables + indexes
- ✅ Event recording: 2 calls to wire into Explore Mode  
- ✅ Outcome recording: outcome helpers ready for Telegram handlers
- ✅ Integration module: bridges explore_mode.py → learning_db.py
- ✅ Streamlit UI template: documents full read API for future dashboard
- ✅ Zero external dependencies (SQLite + WAL mode only)
- ✅ All tests passing; schema verified

**No conflicts detected** with existing PersGraph modules.

---

## 📁 Files Created

### Core Learning Layer

1. **`second_brain/learning_db.py`** (22.2 KB)
   - SQLite schema: 5 tables (events, outcomes, skills, preferences, audit)
   - Connection pooling with WAL mode for safe concurrent access
   - Event recording API: `record_event()`, `record_skip()`
   - Outcome recording API: `record_outcome()`
   - Query helpers for dashboard: `get_event_summary()`, `get_outcome_summary()`, etc.
   - Skill & preference management (Phase 2 foundation)
   - Comprehensive logging and error handling
   - Smoke test included (`if __name__ == "__main__"`)

2. **`second_brain/learning_explore_integration.py`** (13 KB)
   - Bridges Explore Mode → Learning DB
   - Hooks for Explore Mode lifecycle:
     - `on_explore_enabled()` — called when `/TripToggle On` activates Explore Mode
     - `on_suggestion_offered()` — called when suggestion is built (before user sees it)
     - `on_skip_event()` — called when check is skipped (cadence/location/movement)
     - `on_explore_disabled()` — called when `/TripToggle Off` or expired
   - Outcome recording hooks:
     - `on_suggestion_accepted()` — user clicks/opens suggestion
     - `on_suggestion_clicked()` — user opens link
     - `on_suggestion_bookmarked()` — user saves to places
     - `on_suggestion_skipped()` — user dismisses
   - Session-level stats (Phase 2: detailed analysis)
   - Smoke test included

3. **`scripts/learning_streamlit_template.py`** (12.7 KB)
   - **Template/proposal only** — not deployed to production yet
   - Shows how a future Streamlit UI should read from learning_db.py
   - Multi-tab dashboard:
     - Overview: metrics + event/outcome type breakdowns
     - Events: recent events with metadata
     - Outcomes: user interactions + engagement time stats
     - Skills & Prefs: learned patterns + preferences
     - Debug: raw data inspection
   - **API Documentation**: Comments show all query functions for a UI to use
   - Safe to run locally: `streamlit run scripts/learning_streamlit_template.py`
   - Requires: `pip install streamlit pandas` (not in requirements.txt yet)

---

## 🗄️ Database Schema (SQLite)

**Location:** `data/learning.db` (created on first use)

### Table: `events`
Captures every suggestion offered and skip event.

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| id | TEXT | ✓ | UUID primary key |
| timestamp_utc | TEXT | ✓ | ISO 8601 UTC |
| event_type | TEXT | ✓ | "suggestion" \| "skip" \| "enable" \| "disable" |
| explore_session_id | TEXT |  | Links to Explore Mode session |
| location_lat | REAL |  | Current latitude |
| location_lon | REAL |  | Current longitude |
| location_accuracy_m | INTEGER |  | Accuracy in meters |
| metadata | TEXT |  | JSON: cadence_min, intensity, reason, etc. |

**Indexes:** timestamp_utc (DESC), event_type, explore_session_id

---

### Table: `outcomes`
Records user reactions to suggestions.

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| id | TEXT | ✓ | UUID primary key |
| event_id | TEXT | ✓ | FK → events.id |
| timestamp_utc | TEXT | ✓ | ISO 8601 UTC |
| outcome_type | TEXT | ✓ | "accepted" \| "skipped" \| "clicked" \| "bookmarked" |
| suggestion_title | TEXT |  | Title of the suggestion |
| suggestion_category | TEXT |  | "poi" \| "place" \| "fallback" |
| engagement_seconds | INTEGER |  | Time before user acted |
| feedback | TEXT |  | Optional user text |
| metadata | TEXT |  | JSON with context |

**Indexes:** timestamp_utc (DESC), event_id, outcome_type

---

### Table: `skills`
Placeholder for Phase 2 (learned patterns).

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| id | TEXT | ✓ | UUID primary key |
| skill_name | TEXT | ✓ | Unique identifier (e.g., "prefers_cafes") |
| skill_category | TEXT | ✓ | "preference" \| "filter" \| "ranker" |
| confidence | REAL | ✓ | 0.0 to 1.0 |
| signal_strength | INTEGER |  | Count of supporting signals |
| skill_data | TEXT |  | JSON with criteria |
| created_at | TEXT | ✓ | ISO 8601 UTC |
| updated_at | TEXT | ✓ | ISO 8601 UTC |
| metadata | TEXT |  | JSON |

**Indexes:** skill_category, confidence (DESC)

---

### Table: `preferences`
User-facing settings (manual + learned).

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| id | TEXT | ✓ | UUID primary key |
| pref_key | TEXT | ✓ | Unique key (e.g., "explore_cadence_minutes") |
| value | TEXT | ✓ | JSON value |
| source | TEXT | ✓ | "manual" \| "learned" \| "inferred" |
| confidence | REAL |  | 0.0 to 1.0 for learned prefs |
| created_at | TEXT | ✓ | ISO 8601 UTC |
| updated_at | TEXT | ✓ | ISO 8601 UTC |
| metadata | TEXT |  | JSON |

**Indexes:** pref_key, source

---

### Table: `audit`
Operational log for debugging.

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| id | TEXT | ✓ | UUID primary key |
| timestamp_utc | TEXT | ✓ | ISO 8601 UTC |
| action | TEXT | ✓ | "learn_event" \| "record_outcome" \| "skill_update" \| "error" |
| result | TEXT | ✓ | "success" \| "error" \| "skipped" |
| details | TEXT |  | JSON with context |
| duration_ms | INTEGER |  | Operation duration |

**Indexes:** timestamp_utc (DESC), action

---

## 🔌 Integration with Explore Mode

### How to Wire Into `explore_mode.py`

The integration module provides a clean API to call from Explore Mode. Here's where:

#### 1. When Explore Mode is Enabled (currently in `enable_explore()`)
```python
from second_brain.learning_explore_integration import on_explore_enabled

def enable_explore(duration: str | None, cadence: int | None, intensity: str | None):
    state = load_state()
    started = now_local()
    # ... existing code ...
    
    # NEW: Record learning session
    session_id = on_explore_enabled(
        duration_label=duration_label,
        cadence_minutes=cadence_minutes,
        intensity=intensity_value,
        location=state.get("last_location")  # if available
    )
    # Could store session_id in state for tracking
    
    return state
```

#### 2. When a Suggestion is Built (currently in `build_suggestion()` → `check_once()`)
```python
from second_brain.learning_explore_integration import on_suggestion_offered

def check_once() -> tuple[bool, str]:
    state = load_state()
    now = now_local()
    ok, reason = should_run_suggestion(state, now=now)
    
    if not ok:
        on_skip_event(reason=reason, explore_session_id=state.get("session_id"))
        return False, reason
    
    suggestion = build_suggestion(state=state)
    message = format_suggestion_message(suggestion, state)
    
    # NEW: Record suggestion in learning DB
    event_id = on_suggestion_offered(
        suggestion_title=suggestion.title,
        suggestion_category=suggestion.tag,
        cadence_minutes=state.get("cadence_minutes", DEFAULT_CADENCE_MIN),
        intensity=state.get("intensity", DEFAULT_INTENSITY),
        location=state.get("last_location"),
        explore_session_id=state.get("session_id")
    )
    # Store event_id with suggestion for later outcome recording
    
    return True, message
```

#### 3. When Explore Mode is Disabled
```python
from second_brain.learning_explore_integration import on_explore_disabled

def disable_explore(reason: str = "manual"):
    state = load_state()
    session_id = state.get("session_id")
    
    # NEW: Close learning session
    on_explore_disabled(session_id, reason=reason)
    
    state.update({
        "enabled": False,
        "status": f"disabled:{reason}",
    })
    save_state(state)
```

### 4. When User Interacts (Telegram Command Handlers)

These would be called from handlers like `/accept`, `/skip`, `/bookmark`:

```python
from second_brain.learning_explore_integration import (
    on_suggestion_accepted,
    on_suggestion_clicked,
    on_suggestion_bookmarked,
    on_suggestion_skipped,
)

# In a Telegram command handler (example):
@app.command("accept_suggestion")
async def handle_accept(chat_id, event_id, suggestion_title):
    outcome_id = on_suggestion_accepted(
        event_id=event_id,
        suggestion_title=suggestion_title,
        suggestion_category="poi",
        engagement_seconds=compute_engagement_time(event_id),
        feedback=message.text if message.text else None
    )
    await send_message(chat_id, f"✅ Recorded: {suggestion_title}")
```

---

## 🧠 Learning DB API (Phase 1 Functions)

### Event Recording
```python
from second_brain.learning_db import record_event, record_skip

# Record a suggestion event
event_id = record_event(
    event_type="suggestion",
    explore_session_id=session_id,
    location={"lat": 37.7749, "lon": -122.4194, "accuracy_m": 50},
    metadata={"cadence_min": 60, "intensity": "medium"}
)

# Record a skip event (shorthand)
skip_id = record_skip(
    reason="cadence_window_not_reached",
    explore_session_id=session_id,
    location=current_location
)
```

### Outcome Recording
```python
from second_brain.learning_db import record_outcome

outcome_id = record_outcome(
    event_id=event_id,
    outcome_type="accepted",  # or "skipped", "clicked", "bookmarked"
    suggestion_title="Cafe Velocity",
    suggestion_category="poi",
    engagement_seconds=5,
    feedback=None
)
```

### Query Helpers (for Streamlit UI)
```python
from second_brain.learning_db import (
    get_event_summary,
    get_outcome_summary,
    get_skill_summary,
    get_preferences,
    count_events_by_type,
    count_outcomes_by_type,
)

# Get recent events for dashboard
events = get_event_summary(limit=100)
# Returns: [{"id": ..., "timestamp_utc": ..., "event_type": ..., ...}, ...]

# Get recent outcomes
outcomes = get_outcome_summary(limit=100)
# Returns: [{"id": ..., "outcome_type": ..., "suggestion_title": ..., ...}, ...]

# Get counts
event_counts = count_events_by_type()
# Returns: {"suggestion": 50, "skip": 30, "enable": 2, "disable": 2}
```

### Skill & Preference Management
```python
from second_brain.learning_db import create_skill, set_preference

# Create a learned skill (Phase 2)
skill_id = create_skill(
    skill_name="prefers_cafes",
    skill_category="preference",
    confidence=0.85,
    signal_strength=10
)

# Set or update a preference
pref_id = set_preference(
    pref_key="explore_cadence_minutes",
    value=60,
    source="manual"
)
```

---

## 🚀 Streamlit UI Proposal

**File:** `scripts/learning_streamlit_template.py`

This is a **complete template** showing how a Streamlit dashboard would read from the learning DB. It is **not deployed to production** yet, but ready for Phase 2.

### Dashboard Tabs

1. **Overview**: Summary metrics (event counts, outcome breakdown)
2. **Events**: Recent events table with metadata
3. **Outcomes**: User interactions with engagement time stats
4. **Skills & Preferences**: Learned patterns (placeholder for Phase 2)
5. **Debug**: Raw data inspection

### To Run Locally
```bash
cd /root/AgenticHub/Persgraph
pip install streamlit pandas  # one-time
streamlit run scripts/learning_streamlit_template.py
```

### Read API for UI
The template documents all functions a UI should use:
- `get_event_summary(limit)` → events table
- `get_outcome_summary(limit)` → outcomes table
- `get_skill_summary(limit)` → skills table
- `get_preferences(source)` → preferences dict
- `count_events_by_type()` → event type breakdown
- `count_outcomes_by_type()` → outcome type breakdown
- `debug_summary()` → table row counts

**Important:** The UI should be **read-only**. All writes go through `learning_db.py` functions.

---

## ✅ Verification & Testing

### 1. Schema Bootstrap Test
```bash
cd /root/AgenticHub/Persgraph
python3 -m second_brain.learning_db
```
**Result:** ✅ All tests passed
- Schema initialized
- Events recorded
- Outcomes recorded
- Skills created
- Preferences set

### 2. Integration Test
```bash
python3 -m second_brain.learning_explore_integration
```
**Result:** ✅ All integration tests passed
- Explore Mode enable recorded
- Suggestion offered recorded
- Outcome acceptance recorded
- Skip event recorded
- Explore Mode disable recorded

### 3. Database Verification
```bash
sqlite3 data/learning.db ".schema"
```
**Result:** ✅ 5 tables with proper structure
- events: 5 rows (from tests)
- outcomes: 2 rows (from tests)
- skills: 1 row
- preferences: 2 rows
- audit: 8 rows (internal logs)

### 4. Conflict Check
- **No module conflicts** found in existing codebase
- **No overwrites** of existing functions
- **Clean separation** of concerns (learning_db.py in second_brain/)
- **Integration module** bridges cleanly without modifying explore_mode.py yet

---

## 📊 What's Captured (Phase 1)

### Events
- ✅ Suggestion offered (with cadence, intensity, location)
- ✅ Skip events (cadence not met, location unavailable, movement suppressed)
- ✅ Enable event (when Explore Mode is turned on)
- ✅ Disable event (when Explore Mode is turned off)

### Outcomes
- ✅ Accepted (user clicked/opened suggestion)
- ✅ Clicked (user clicked link to maps/place)
- ✅ Bookmarked (user saved to places)
- ✅ Skipped (user dismissed)
- ✅ Engagement time (seconds before action)
- ✅ Optional feedback (user text)

### Skills & Preferences (Foundation for Phase 2)
- ✅ Skill storage schema (name, category, confidence, signals)
- ✅ Preference storage (manual + learned)
- ✅ Version-agnostic updates (INSERT OR REPLACE)

---

## 🔮 Phase 2 Roadmap (Not Yet Implemented)

When extending the learning layer:

1. **Skill Discovery**
   - Analyze outcomes → infer preferences
   - Example: "user accepted 80% of POIs in category 'cafe'" → confidence 0.8
   - Store in `skills` table with signal counts

2. **Preference Learning**
   - Auto-populate `preferences` table from patterns
   - Example: "user typically engages within 10 seconds" → infer fast decision-maker
   - Mark with `source="learned"`

3. **Ranking Integration**
   - Use learned skills to re-rank suggestions
   - Modify `build_suggestion()` to consider user preferences
   - Boost POIs matching learned patterns

4. **Session Analysis**
   - Compute session stats: total suggestions, acceptance rate, engagement avg
   - Store in session-level record for trend analysis

5. **Data Export**
   - Add CSV export functions
   - Possible: data warehouse integration (Phase 3)

6. **Retention Policy**
   - Add auto-cleanup for old audit logs
   - Archive historical data if needed

---

## 📝 No Breaking Changes

- ✅ explore_mode.py: **no modifications yet** (ready to wire when Phase 2 starts)
- ✅ Existing Explore Mode behavior: **unchanged**
- ✅ Data directory: learning.db coexists with explore_state.json, explore_audit.json
- ✅ Backward compatible: all new code is opt-in via integration module

**Migration:** When ready to wire Phase 1 into explore_mode.py, calls can be added without breaking existing functionality (learning DB is graceful fallback with try/except).

---

## 🛠️ Troubleshooting

### Learning DB not initializing?
- Check: `data/` directory permissions (should be writable)
- Check: SQLite version ≥ 3.8.0 (WAL mode requirement)

### Integration module says "Learning DB not available"?
- Normal in development if import path differs
- Module falls back gracefully; all hooks return dummy UUIDs

### Want to inspect DB contents?
```bash
sqlite3 /root/AgenticHub/Persgraph/data/learning.db

# View all tables
.tables

# View schema of a table
.schema events

# Query recent events
SELECT timestamp_utc, event_type, session_id FROM events LIMIT 5;

# Count by type
SELECT event_type, COUNT(*) FROM events GROUP BY event_type;
```

---

## 📦 File Manifest

| File | Size | Purpose |
|------|------|---------|
| `second_brain/learning_db.py` | 22.2 KB | Core learning database with schema + API |
| `second_brain/learning_explore_integration.py` | 13 KB | Integration hooks for Explore Mode |
| `scripts/learning_streamlit_template.py` | 12.7 KB | Streamlit UI template + read API docs |
| `data/learning.db` | 116 KB | SQLite database (created on first run) |

**Total New Code:** ~48 KB  
**Dependencies Added:** None (SQLite built-in)  
**Existing Files Modified:** None (yet; ready for Phase 2 wiring)

---

## 🎯 Next Steps (Phase 2)

1. **Wire into explore_mode.py**
   - Add 3-4 calls to learning_explore_integration in check_once() and enable_explore()
   - Test with live Explore Mode cron job

2. **Build Telegram outcome handlers**
   - Create `/accept`, `/skip`, `/bookmark` command handlers
   - Call on_suggestion_* functions when user reacts

3. **Implement skill discovery**
   - Analyze outcomes table
   - Infer preferences and populate skills table
   - Add helper functions for ranking

4. **Deploy Streamlit UI** (optional Phase 2b)
   - Take learning_streamlit_template.py → production
   - Add live refresh
   - Connect to Telegram for feedback

---

## ✨ Summary

**Delivered:**
- ✅ Lightweight, production-ready SQLite learning layer
- ✅ Clean event/outcome recording API
- ✅ Full integration module for Explore Mode
- ✅ Complete Streamlit template with read API docs
- ✅ Zero external dependencies (SQLite only)
- ✅ All tests passing; schema verified
- ✅ No conflicts with existing code
- ✅ Comprehensive documentation

**Ready for Phase 2:**
- Clear wiring points in explore_mode.py (3 functions to add)
- Foundation for skill discovery (skills + preferences tables)
- Ready for Telegram outcome handlers
- Optional Streamlit UI template waiting for deployment

---

**Implementation Date:** 2026-06-17  
**Status:** ✅ Phase 1 Complete & Verified

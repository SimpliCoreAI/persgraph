# PersGraph Explore Mode — Product Feature Specification

**Location:** `features/explore-mode/FEATURE.md`  
**Status:** Design Phase (All 3 Phases Defined)  
**Last Updated:** 2026-06-14

---

## Overview

Explore Mode transforms PersGraph into a **location-aware travel and local discovery companion**. When enabled via `/TripToggle On|Off`, it periodically sends curated nearby place suggestions directly to Telegram, powered by GPT and matched against saved places, bucket-list items, and contextual signals like weather and available time.

**Core idea:** Instead of a user manually searching for "what's nearby," PersGraph proactively nudges them with thoughtful, personalized suggestions aligned with their travel context and preferences.

This feature is additive to existing PersGraph travel, bucket-list, and Morning Brief capabilities. It does **not** replace `/place`, `/bucketlist`, `/schedule`, or Morning Brief. It uses them as context.

---

## Core Commands

### `/TripToggle On [duration] [cadence] [intensity]`
Enable Explore Mode with optional duration, cadence, and intensity.

**Syntax:**
```
/TripToggle On
/TripToggle On 4h
/TripToggle On trip 30m high
/TripToggle On 2h 60m medium
```

**Defaults:**
- duration: `2h` (hours) | `eod` (end of day) | `trip` (indefinite until next toggle)
- cadence: `60m` (minutes)
- intensity: `medium`

**Response:**
```text
✅ Explore Mode: ON
⏱ Duration: 2 hours
📍 Cadence: every 60 minutes
🎯 Intensity: medium
🗺 Location-aware suggestions: active

You'll get nearby ideas while Explore Mode is on.
```

### `/TripToggle Off`
Disable Explore Mode immediately.

**Response:**
```text
🛑 Explore Mode: OFF

No more nearby suggestions will be sent.
```

---

## State & Persistence

### Explore Mode State File
**Location:** `data/explore_state.json`

```json
{
  "enabled": true,
  "started_at": "2026-06-14T18:30:00-07:00",
  "duration_minutes": 120,
  "cadence_minutes": 60,
  "intensity": "medium",
  "last_suggestion_at": "2026-06-14T18:35:00-07:00",
  "last_location": {
    "lat": 37.7749,
    "lon": -122.4194,
    "source": "device_gps",
    "accuracy_m": 50
  },
  "suppression_cooldown_minutes": 15,
  "suggested_places_session": [
    "muir-woods-national-monument",
    "ferry-building-marketplace"
  ]
}
```

### Cron Job
- **Job name:** `PersGraph Explore Mode`
- **Schedule:** Every 5 minutes (checks if Explore Mode is active; runs suggestion logic if so)
- **Location source:** Device GPS if available, fallback to manual input via command
- **Output:** Direct Telegram message if suggestion meets threshold

---

## Phases

### Phase 1 — MVP Explore

**Goal:** Get the core loop working end-to-end with simple, useful suggestions.

**Includes:**
- `/TripToggle On|Off` command parsing and state persistence
- cron loop that checks enabled state every 5 minutes
- basic geolocation input (manual or device GPS placeholder)
- nearby POI lookup via GPT + map data
- simple ranking: distance + open status
- one place + one meal suggestion per trigger
- Telegram-only output
- session-based suppression (don’t repeat same suggestion for 15 min)

**Key files:**
- `scripts/explore_mode.py` — core logic
- `scripts/command.py` — add `cmd_explore_toggle()`
- `data/explore_state.json` — state persistence

**Success criteria:**
- toggle works reliably
- cron doesn’t spam
- at least 80% of suggestions are relevant (manual review)
- no crashes on missing location

---

### Phase 2 — Smart Personalization

**Goal:** Make suggestions feel relevant and contextual, not generic.

**Adds:**
- **duration options:** `2h`, `4h`, `8h`, `eod`, `trip`
- **cadence options:** `30m`, `60m`, `90m`
- **intensity levels:** `low`, `medium`, `high`
- **bucket-list matching** — boost saved places
- **saved-place matching** — recognize nearby existing places
- **weather awareness** — suggest indoor options if rainy
- **time-fit awareness** — suggest quick stop vs longer visit
- **deduplication logic** — don’t repeat same suggestion for 4 hours even if it re-ranks high
- **movement detection** — only trigger if user moved significantly since last check

**Key files:**
- `scripts/explore_mode.py` — upgraded ranking logic
- `scripts/explore_weather.py` — weather awareness helper
- places/bucket-list lookup integration from the current PersGraph data layer
- `data/explore_state.json` — enhanced with suppression history

**Success criteria:**
- bucket-list matches are recognized
- weather-aware suggestions improve satisfaction
- cadence/intensity settings are actually honored
- users don’t feel spammed

---

### Phase 3 — Advanced & Trip-Aware

**Goal:** Make Explore Mode feel genuinely personal and trip-conscious.

**Adds:**
- **family / kid-friendly mode** — boost kid-safe, open-ended activities
- **budget awareness** — suggest low-cost options vs premium dining
- **dietary preferences** — filter restaurants by saved preferences
- **trip timeline awareness** — early/mid/late trip suggestions
- **richer historical/cultural context** — blend in learned context about nearby places
- **serendipity mode** — hidden-gem suggestions with slightly lower relevance bar
- **feedback loop** — learn from ignored vs saved/completed suggestions
- **multi-city trip support** — recognize travel context and adjust cadence/intensity
- **cross-feature integration** — surface links to saved notes, bucket-list, or ingested travel content

**Key files:**
- `scripts/explore_mode.py`
- `scripts/explore_learner.py`
- `data/explore_preferences.json`
- `data/explore_feedback_log.json`
- `data/explore_audit.json`

**Success criteria:**
- family mode improves relevance for outings
- serendipity suggestions lead to genuine discovery moments
- multi-city trips are handled smoothly
- cross-feature integration feels natural

---

## Conflict Avoidance & Integration

### Existing PersGraph Features — no conflicts intended

| Feature | Current Command | Explore Mode relationship |
|---------|------------------|---------------------------|
| Places | `/place`, `/places` | Uses saved places as ranking context |
| Bucket List | `/bucketlist add/list` | Boosts nearby saved bucket-list items |
| Morning Brief | scheduled / digest | Separate daily ritual; Explore is an opt-in ambient layer |
| Schedule | `/schedule` | May later use free-time windows as context |
| Appointment | `/appointment` | May later suppress suggestions around appointments |
| Digest | `/digest` | Separate summary path |
| Ingest | `/ingest`, `/wiki-ingest` | May later surface related travel context |

### Design safeguards
1. **Explicit opt-in only** — user must toggle it on.
2. **Easy off switch** — `/TripToggle Off` or duration expiry.
3. **Separate state file** — no mutation of places DB or note DB required for Phase 1.
4. **No command collision** — `/TripToggle` is a unique namespace.
5. **Graceful degradation** — missing location means no suggestion, not an error storm.
6. **No Morning Brief overlap** — Explore is context-aware discovery, not a replacement for the daily digest.
7. **No unsolicited permanent location logging** — only minimal session state required for cadence/suppression.

---

## Execution Model

### Cron setup
```bash
Job Name: PersGraph Explore Mode
Schedule: Every 5 minutes
Command: cd ~/AgenticHub/Persgraph && PYTHONPATH=. .venv/bin/python scripts/explore_mode.py --check
```

### Logic flow
1. Load `explore_state.json`
2. Exit if not enabled or duration expired
3. Exit if cadence window has not elapsed
4. Resolve current location (GPS first, fallback chain later)
5. Exit quietly if location is unavailable
6. Rank nearby POIs + meal options
7. Suppress duplicates / low-value suggestions
8. Send formatted Telegram message when threshold is met
9. Update state + audit trail

### Location input preference
1. Device GPS (if available from OpenClaw/node integration)
2. Manual location passed or stored from toggle/session
3. Last known trip/place context
4. Future fallback: ask user for a city or area if needed

---

## Sample Outputs

### Nearby landmark
```text
🗺 Explore Nearby

📍 Muir Woods National Monument
↳ 2.4 km away • scenic redwood trails
↳ Great fit if you want a calm 60–90 min nature stop

🍽 Nearby bite: Pelican Inn
↳ classic pub-style lunch nearby

💡 Good match if you're in explore mode for nature + local character.
```

### Rain-friendly option
```text
🌧 Rain-friendly nearby idea

📍 Asian Art Museum
↳ indoor, easy to explore at your own pace
↳ strong option for a wet afternoon

🍜 Nearby meal: casual ramen or small-plates stop

💡 Better fit than outdoor walking right now.
```

### Saved bucket-list match
```text
⭐ Bucket-list match nearby

📍 Port Costa
↳ You already saved this place
↳ Americana vibe, historic feel, scenic nearby stretch

🍽 Worth pairing with: Warehouse Cafe or Bull Valley Roadhouse

💡 Since this is already on your list, this is a higher-priority suggestion.
```

### Family outing
```text
👨‍👩‍👧‍👦 Family-friendly nearby

📍 Waterfront trail + open park stop
↳ room to walk, snack, and hang out
↳ easier with kids than a long museum stop

🍦 Bonus: nearby dessert / casual food option

💡 Good low-friction outing for 45–75 minutes.
```

---

## Future Notes

- Phase 1 should prove the loop without overbuilding.
- Phase 2 is where PersGraph becomes genuinely useful for real-world travel.
- Phase 3 is where it starts to feel personal instead of generic.
- The user-facing value is selective, high-quality discovery — not notification spam.

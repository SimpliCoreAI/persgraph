"""
PersGraph Learning Layer — Phase 1 SQLite Schema & Helpers

Lightweight learning database for Explore Mode suggestion tracking.
Captures user interactions (accepts, skips, engagements) to enable
future personalization and outcome analysis.

DB file: data/learning.db (local, no external deps)
"""

from __future__ import annotations

import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "learning.db"
SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# DB Connection & Schema Bootstrap
# ---------------------------------------------------------------------------

def _conn() -> sqlite3.Connection:
    """Get or create SQLite connection with WAL mode."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Initialize learning layer tables if not present."""
    conn.executescript("""
        -- Metadata: track schema version
        CREATE TABLE IF NOT EXISTS _meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        -- Events: suggestions, skips, interactions
        -- Captures every suggestion offered and user action on it
        CREATE TABLE IF NOT EXISTS events (
            id                  TEXT PRIMARY KEY,
            timestamp_utc       TEXT NOT NULL,           -- ISO 8601 UTC
            event_type          TEXT NOT NULL,           -- "suggestion" | "skip" | "accept" | "engage"
            explore_session_id  TEXT,                    -- Links to explore_state session
            location_lat        REAL,
            location_lon        REAL,
            location_accuracy_m INTEGER,
            metadata            TEXT                     -- JSON: {cadence_min, intensity, reason, ...}
        );
        CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp_utc DESC);
        CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
        CREATE INDEX IF NOT EXISTS idx_events_session ON events(explore_session_id);

        -- Outcomes: user reactions to suggestions
        -- Recorded when user interacts with suggestion (accept, skip, click, bookmark)
        CREATE TABLE IF NOT EXISTS outcomes (
            id                  TEXT PRIMARY KEY,
            event_id            TEXT NOT NULL,           -- FK to events
            timestamp_utc       TEXT NOT NULL,           -- ISO 8601 UTC
            outcome_type        TEXT NOT NULL,           -- "accepted" | "skipped" | "clicked" | "bookmarked"
            suggestion_title    TEXT,
            suggestion_category TEXT,                    -- "poi" | "place" | "fallback"
            engagement_seconds  INTEGER,                 -- Time before action
            feedback            TEXT,                    -- Optional user feedback
            metadata            TEXT,                    -- JSON
            FOREIGN KEY(event_id) REFERENCES events(id)
        );
        CREATE INDEX IF NOT EXISTS idx_outcomes_timestamp ON outcomes(timestamp_utc DESC);
        CREATE INDEX IF NOT EXISTS idx_outcomes_event ON outcomes(event_id);
        CREATE INDEX IF NOT EXISTS idx_outcomes_type ON outcomes(outcome_type);

        -- Skills: learned patterns for future suggestions
        -- Phase 2: populated from outcomes; used for ranking/filtering
        CREATE TABLE IF NOT EXISTS skills (
            id                  TEXT PRIMARY KEY,
            skill_name          TEXT NOT NULL UNIQUE,   -- e.g. "prefers_restaurants", "avoids_expensive"
            skill_category      TEXT NOT NULL,          -- "preference" | "filter" | "ranker"
            confidence          REAL NOT NULL DEFAULT 0.0,  -- 0.0 to 1.0
            signal_strength     INTEGER DEFAULT 0,       -- count of signals supporting skill
            skill_data          TEXT,                    -- JSON: {criteria, weights, ...}
            created_at          TEXT NOT NULL,
            updated_at          TEXT NOT NULL,
            metadata            TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_skills_category ON skills(skill_category);
        CREATE INDEX IF NOT EXISTS idx_skills_confidence ON skills(confidence DESC);

        -- Preferences: user-facing settings & learned attributes
        -- Phase 1: stores manual prefs; Phase 2: auto-discovered from outcomes
        CREATE TABLE IF NOT EXISTS preferences (
            id                  TEXT PRIMARY KEY,
            pref_key            TEXT NOT NULL UNIQUE,   -- e.g. "explore_intensity", "favorite_cuisines"
            value               TEXT NOT NULL,          -- JSON
            source              TEXT NOT NULL,          -- "manual" | "learned" | "inferred"
            confidence          REAL DEFAULT 0.5,       -- For learned prefs
            created_at          TEXT NOT NULL,
            updated_at          TEXT NOT NULL,
            metadata            TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_prefs_key ON preferences(pref_key);
        CREATE INDEX IF NOT EXISTS idx_prefs_source ON preferences(source);

        -- Audit: operational log for debugging & monitoring
        CREATE TABLE IF NOT EXISTS audit (
            id                  TEXT PRIMARY KEY,
            timestamp_utc       TEXT NOT NULL,           -- ISO 8601 UTC
            action              TEXT NOT NULL,           -- "learn_event" | "record_outcome" | "skill_update" | "error"
            result              TEXT NOT NULL,           -- "success" | "error" | "skipped"
            details             TEXT,                    -- JSON with context
            duration_ms         INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit(timestamp_utc DESC);
        CREATE INDEX IF NOT EXISTS idx_audit_action ON audit(action);
    """)


# ---------------------------------------------------------------------------
# Event Recording (Explore Mode Integration)
# ---------------------------------------------------------------------------

def record_event(
    event_type: str,
    explore_session_id: str | None = None,
    location: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """
    Record an event in the learning layer.
    
    Args:
        event_type: "suggestion" | "skip" | "accept" | "engage"
        explore_session_id: link to Explore Mode session (optional)
        location: {lat, lon, accuracy_m, source} (optional)
        metadata: arbitrary JSON context (cadence_min, intensity, reason, etc.)
    
    Returns:
        Event ID (UUID)
    """
    event_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    loc_lat = location.get("lat") if location else None
    loc_lon = location.get("lon") if location else None
    loc_acc = location.get("accuracy_m") if location else None
    
    meta_json = json.dumps(metadata or {})
    
    try:
        conn = _conn()
        conn.execute("""
            INSERT INTO events
            (id, timestamp_utc, event_type, explore_session_id,
             location_lat, location_lon, location_accuracy_m, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event_id, now, event_type, explore_session_id,
            loc_lat, loc_lon, loc_acc, meta_json
        ))
        conn.commit()
        conn.close()
        
        _audit_action("learn_event", "success", {
            "event_id": event_id,
            "event_type": event_type,
            "session_id": explore_session_id
        })
        return event_id
    except Exception as e:
        logger.error(f"Failed to record event: {e}")
        _audit_action("learn_event", "error", {"error": str(e)})
        return ""


def record_outcome(
    event_id: str,
    outcome_type: str,
    suggestion_title: str | None = None,
    suggestion_category: str | None = None,
    engagement_seconds: int | None = None,
    feedback: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """
    Record outcome of a suggestion (user reaction).
    
    Args:
        event_id: ID of the event that prompted this outcome
        outcome_type: "accepted" | "skipped" | "clicked" | "bookmarked"
        suggestion_title: title of the suggestion
        suggestion_category: "poi" | "place" | "fallback"
        engagement_seconds: elapsed time before action
        feedback: optional user text
        metadata: arbitrary JSON context
    
    Returns:
        Outcome ID (UUID)
    """
    outcome_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    meta_json = json.dumps(metadata or {})
    
    try:
        conn = _conn()
        conn.execute("""
            INSERT INTO outcomes
            (id, event_id, timestamp_utc, outcome_type,
             suggestion_title, suggestion_category, engagement_seconds, feedback, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            outcome_id, event_id, now, outcome_type,
            suggestion_title, suggestion_category, engagement_seconds, feedback, meta_json
        ))
        conn.commit()
        conn.close()
        
        _audit_action("record_outcome", "success", {
            "outcome_id": outcome_id,
            "outcome_type": outcome_type,
            "event_id": event_id
        })
        return outcome_id
    except Exception as e:
        logger.error(f"Failed to record outcome: {e}")
        _audit_action("record_outcome", "error", {"error": str(e)})
        return ""


def record_skip(
    explore_session_id: str | None = None,
    reason: str | None = None,
    location: dict[str, Any] | None = None,
) -> str:
    """
    Convenience: record a skip event (Explore Mode cadence not met, etc).
    
    Args:
        explore_session_id: current session ID
        reason: why skipped (e.g. "cadence_window_not_reached", "location_unavailable")
        location: current location context
    
    Returns:
        Event ID
    """
    metadata = {"reason": reason} if reason else {}
    return record_event(
        event_type="skip",
        explore_session_id=explore_session_id,
        location=location,
        metadata=metadata
    )


# ---------------------------------------------------------------------------
# Query Helpers (for Streamlit UI and future analysis)
# ---------------------------------------------------------------------------

def get_event_summary(limit: int = 100) -> list[dict[str, Any]]:
    """
    Get recent events for dashboard overview.
    Intended for Streamlit UI reading.
    
    Returns:
        List of dicts: {id, timestamp_utc, event_type, session_id, metadata}
    """
    try:
        conn = _conn()
        rows = conn.execute("""
            SELECT id, timestamp_utc, event_type, explore_session_id, metadata
            FROM events
            ORDER BY timestamp_utc DESC
            LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        
        result = []
        for row in rows:
            meta = json.loads(row["metadata"] or "{}")
            result.append({
                "id": row["id"],
                "timestamp_utc": row["timestamp_utc"],
                "event_type": row["event_type"],
                "session_id": row["explore_session_id"],
                "metadata": meta,
            })
        return result
    except Exception as e:
        logger.error(f"Failed to get event summary: {e}")
        return []


def get_outcome_summary(limit: int = 100) -> list[dict[str, Any]]:
    """
    Get recent outcomes for dashboard analysis.
    Intended for Streamlit UI reading.
    
    Returns:
        List of dicts: {id, outcome_type, suggestion_title, timestamp_utc, engagement_seconds}
    """
    try:
        conn = _conn()
        rows = conn.execute("""
            SELECT id, timestamp_utc, outcome_type, suggestion_title,
                   suggestion_category, engagement_seconds, feedback
            FROM outcomes
            ORDER BY timestamp_utc DESC
            LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        
        result = []
        for row in rows:
            result.append({
                "id": row["id"],
                "timestamp_utc": row["timestamp_utc"],
                "outcome_type": row["outcome_type"],
                "suggestion_title": row["suggestion_title"],
                "suggestion_category": row["suggestion_category"],
                "engagement_seconds": row["engagement_seconds"],
                "feedback": row["feedback"],
            })
        return result
    except Exception as e:
        logger.error(f"Failed to get outcome summary: {e}")
        return []


def get_skill_summary(limit: int = 50) -> list[dict[str, Any]]:
    """
    Get learned skills for dashboard.
    Intended for Streamlit UI reading.
    
    Returns:
        List of dicts: {id, skill_name, category, confidence, signal_strength, metadata}
    """
    try:
        conn = _conn()
        rows = conn.execute("""
            SELECT id, skill_name, skill_category, confidence, signal_strength, skill_data
            FROM skills
            ORDER BY confidence DESC, signal_strength DESC
            LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        
        result = []
        for row in rows:
            skill_data = json.loads(row["skill_data"] or "{}")
            result.append({
                "id": row["id"],
                "skill_name": row["skill_name"],
                "category": row["skill_category"],
                "confidence": row["confidence"],
                "signal_strength": row["signal_strength"],
                "skill_data": skill_data,
            })
        return result
    except Exception as e:
        logger.error(f"Failed to get skill summary: {e}")
        return []


def get_preferences(source: str | None = None) -> dict[str, Any]:
    """
    Get user preferences (manual + learned).
    Intended for Streamlit UI and future suggestion ranking.
    
    Args:
        source: filter by "manual", "learned", "inferred" (None = all)
    
    Returns:
        Dict: {pref_key: value}
    """
    try:
        conn = _conn()
        if source:
            rows = conn.execute("""
                SELECT pref_key, value FROM preferences WHERE source = ?
                ORDER BY updated_at DESC
            """, (source,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT pref_key, value FROM preferences
                ORDER BY updated_at DESC
            """).fetchall()
        conn.close()
        
        result = {}
        for row in rows:
            try:
                result[row["pref_key"]] = json.loads(row["value"])
            except json.JSONDecodeError:
                result[row["pref_key"]] = row["value"]
        return result
    except Exception as e:
        logger.error(f"Failed to get preferences: {e}")
        return {}


def count_events_by_type() -> dict[str, int]:
    """Count events by type for dashboard summary."""
    try:
        conn = _conn()
        rows = conn.execute("""
            SELECT event_type, COUNT(*) as count
            FROM events
            GROUP BY event_type
        """).fetchall()
        conn.close()
        
        return {row["event_type"]: row["count"] for row in rows}
    except Exception as e:
        logger.error(f"Failed to count events: {e}")
        return {}


def count_outcomes_by_type() -> dict[str, int]:
    """Count outcomes by type for dashboard summary."""
    try:
        conn = _conn()
        rows = conn.execute("""
            SELECT outcome_type, COUNT(*) as count
            FROM outcomes
            GROUP BY outcome_type
        """).fetchall()
        conn.close()
        
        return {row["outcome_type"]: row["count"] for row in rows}
    except Exception as e:
        logger.error(f"Failed to count outcomes: {e}")
        return {}


# ---------------------------------------------------------------------------
# Skill Management (Phase 2 foundation)
# ---------------------------------------------------------------------------

def create_skill(
    skill_name: str,
    skill_category: str,
    confidence: float = 0.0,
    signal_strength: int = 0,
    skill_data: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """
    Create or update a learned skill (preference, filter, ranker).
    
    Args:
        skill_name: unique identifier (e.g. "prefers_italian")
        skill_category: "preference" | "filter" | "ranker"
        confidence: 0.0 to 1.0
        signal_strength: number of supporting signals
        skill_data: arbitrary JSON with criteria
        metadata: arbitrary JSON
    
    Returns:
        Skill ID
    """
    skill_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    skill_data_json = json.dumps(skill_data or {})
    meta_json = json.dumps(metadata or {})
    
    try:
        conn = _conn()
        # Try insert; if exists, update instead
        conn.execute("""
            INSERT OR REPLACE INTO skills
            (id, skill_name, skill_category, confidence, signal_strength, skill_data, created_at, updated_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            skill_id, skill_name, skill_category, confidence, signal_strength,
            skill_data_json, now, now, meta_json
        ))
        conn.commit()
        conn.close()
        
        _audit_action("skill_update", "success", {"skill_name": skill_name})
        return skill_id
    except Exception as e:
        logger.error(f"Failed to create skill: {e}")
        _audit_action("skill_update", "error", {"error": str(e)})
        return ""


def set_preference(
    pref_key: str,
    value: Any,
    source: str = "manual",
    confidence: float = 1.0,
) -> str:
    """
    Set or update a preference (manual or learned).
    
    Args:
        pref_key: e.g. "explore_cadence_minutes"
        value: JSON-serializable value
        source: "manual" | "learned" | "inferred"
        confidence: 0.0 to 1.0 (mainly for learned prefs)
    
    Returns:
        Preference ID
    """
    pref_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    value_json = json.dumps(value)
    
    try:
        conn = _conn()
        conn.execute("""
            INSERT OR REPLACE INTO preferences
            (id, pref_key, value, source, confidence, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            pref_id, pref_key, value_json, source, confidence, now, now
        ))
        conn.commit()
        conn.close()
        
        return pref_id
    except Exception as e:
        logger.error(f"Failed to set preference: {e}")
        return ""


# ---------------------------------------------------------------------------
# Audit Log (Internal)
# ---------------------------------------------------------------------------

def _audit_action(
    action: str,
    result: str,
    details: dict[str, Any] | None = None,
    duration_ms: int | None = None,
) -> None:
    """Log internal actions for debugging."""
    audit_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    details_json = json.dumps(details or {})
    
    try:
        conn = _conn()
        conn.execute("""
            INSERT INTO audit (id, timestamp_utc, action, result, details, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (audit_id, now, action, result, details_json, duration_ms))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Audit log failed: {e}")


# ---------------------------------------------------------------------------
# Testing & Debug
# ---------------------------------------------------------------------------


def get_meta(key: str) -> str | None:
    """Read a value from the _meta table."""
    try:
        conn = _conn()
        row = conn.execute("SELECT value FROM _meta WHERE key = ?", (key,)).fetchone()
        conn.close()
        return row["value"] if row else None
    except Exception as e:
        logger.error(f"Failed to get meta {key}: {e}")
        return None


def set_meta(key: str, value: str) -> None:
    """Write a value to the _meta table."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        conn = _conn()
        conn.execute(
            "INSERT OR REPLACE INTO _meta (key, value) VALUES (?, ?)",
            (key, value)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to set meta {key}: {e}")


def get_events_since(cursor_ts: str, limit: int = 1000) -> list[dict[str, Any]]:
    """Get events with timestamp_utc > cursor_ts, ordered ASC."""
    try:
        conn = _conn()
        rows = conn.execute("""
            SELECT id, timestamp_utc, event_type, explore_session_id, metadata
            FROM events
            WHERE timestamp_utc > ?
            ORDER BY timestamp_utc ASC
            LIMIT ?
        """, (cursor_ts, limit)).fetchall()
        conn.close()
        result = []
        for row in rows:
            meta = json.loads(row["metadata"] or "{}")
            result.append({
                "id": row["id"],
                "timestamp_utc": row["timestamp_utc"],
                "event_type": row["event_type"],
                "session_id": row["explore_session_id"],
                "metadata": meta,
            })
        return result
    except Exception as e:
        logger.error(f"Failed to get events since {cursor_ts}: {e}")
        return []


def get_outcomes_since(cursor_ts: str, limit: int = 1000) -> list[dict[str, Any]]:
    """Get outcomes with timestamp_utc > cursor_ts, ordered ASC."""
    try:
        conn = _conn()
        rows = conn.execute("""
            SELECT id, event_id, timestamp_utc, outcome_type,
                   suggestion_title, suggestion_category, engagement_seconds, feedback
            FROM outcomes
            WHERE timestamp_utc > ?
            ORDER BY timestamp_utc ASC
            LIMIT ?
        """, (cursor_ts, limit)).fetchall()
        conn.close()
        result = []
        for row in rows:
            result.append({
                "id": row["id"],
                "event_id": row["event_id"],
                "timestamp_utc": row["timestamp_utc"],
                "outcome_type": row["outcome_type"],
                "suggestion_title": row["suggestion_title"],
                "suggestion_category": row["suggestion_category"],
                "engagement_seconds": row["engagement_seconds"],
                "feedback": row["feedback"],
            })
        return result
    except Exception as e:
        logger.error(f"Failed to get outcomes since {cursor_ts}: {e}")
        return []


def debug_summary() -> dict[str, Any]:
    """Get a quick summary of all tables (for testing)."""
    try:
        conn = _conn()
        counts = {
            "events": conn.execute("SELECT COUNT(*) as c FROM events").fetchone()["c"],
            "outcomes": conn.execute("SELECT COUNT(*) as c FROM outcomes").fetchone()["c"],
            "skills": conn.execute("SELECT COUNT(*) as c FROM skills").fetchone()["c"],
            "preferences": conn.execute("SELECT COUNT(*) as c FROM preferences").fetchone()["c"],
            "audit": conn.execute("SELECT COUNT(*) as c FROM audit").fetchone()["c"],
        }
        conn.close()
        return counts
    except Exception as e:
        logger.error(f"Debug summary failed: {e}")
        return {}


if __name__ == "__main__":
    # Quick smoke test
    print("🧠 Learning DB Smoke Test")
    
    # Test schema bootstrap
    _ensure_schema(_conn())
    print("✓ Schema initialized")
    
    # Test event recording
    eid = record_event(
        "suggestion",
        location={"lat": 37.7749, "lon": -122.4194, "accuracy_m": 50},
        metadata={"cadence_min": 60, "intensity": "medium"}
    )
    print(f"✓ Event recorded: {eid}")
    
    # Test outcome recording
    oid = record_outcome(
        eid,
        "accepted",
        suggestion_title="Coffee Spot",
        suggestion_category="poi",
        engagement_seconds=5
    )
    print(f"✓ Outcome recorded: {oid}")
    
    # Test skill creation
    sid = create_skill(
        "prefers_cafes",
        "preference",
        confidence=0.8,
        signal_strength=3
    )
    print(f"✓ Skill created: {sid}")
    
    # Test preference setting
    pid = set_preference("explore_intensity", "high", source="learned")
    print(f"✓ Preference set: {pid}")
    
    # Test query helpers
    summary = debug_summary()
    print(f"✓ DB Summary: {summary}")
    
    events = get_event_summary(limit=5)
    print(f"✓ Recent events: {len(events)}")
    
    print("\n✅ All tests passed")

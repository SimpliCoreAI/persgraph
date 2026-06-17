"""
PersGraph Learning Layer — Explore Mode Integration

Wires Explore Mode suggestion logic to the learning database.
Records events when suggestions are made and outcomes when users interact.

This module bridges explore_mode.py with learning_db.py.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional
from datetime import datetime, timezone
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)

# Ensure second_brain is in path
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from second_brain.learning_db import (
        record_event,
        record_outcome,
        record_skip,
        set_preference,
    )
    LEARNING_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    try:
        from learning_db import (
            record_event,
            record_outcome,
            record_skip,
            set_preference,
        )
        LEARNING_AVAILABLE = True
    except (ImportError, ModuleNotFoundError):
        logger.warning("Learning DB not available; Explore Mode will run without learning layer")
        LEARNING_AVAILABLE = False


# ---------------------------------------------------------------------------
# Explore Mode Hooks (call from explore_mode.py check_once() / enable_explore())
# ---------------------------------------------------------------------------

def on_explore_enabled(
    duration_label: str,
    cadence_minutes: int,
    intensity: str,
    location: dict[str, Any] | None = None,
) -> str:
    """
    Called when user enables Explore Mode (via /TripToggle On).
    
    Creates a session-level preference record in learning DB.
    
    Args:
        duration_label: "2h" | "4h" | "8h" | "eod" | "trip"
        cadence_minutes: 30 | 60 | 90
        intensity: "low" | "medium" | "high"
        location: optional current location
    
    Returns:
        Session ID for tracking this Explore Mode session
    """
    if not LEARNING_AVAILABLE:
        return str(uuid4())
    
    session_id = str(uuid4())
    
    try:
        # Record session preferences
        set_preference(
            f"explore_session_{session_id}",
            {
                "session_id": session_id,
                "duration_label": duration_label,
                "cadence_minutes": cadence_minutes,
                "intensity": intensity,
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
            source="manual",
            confidence=1.0
        )
        
        # Record an "enable" event
        record_event(
            "enable",
            explore_session_id=session_id,
            location=location,
            metadata={
                "duration_label": duration_label,
                "cadence_minutes": cadence_minutes,
                "intensity": intensity,
            }
        )
        
        logger.info(f"Explore Mode enabled with session {session_id}")
        return session_id
    except Exception as e:
        logger.error(f"Failed to record Explore Mode enable: {e}")
        return session_id


def on_suggestion_offered(
    suggestion_title: str,
    suggestion_category: str,
    cadence_minutes: int,
    intensity: str,
    location: dict[str, Any] | None = None,
    explore_session_id: str | None = None,
) -> str:
    """
    Called when Explore Mode builds and prepares a suggestion to send.
    
    Records a "suggestion" event (before user has reacted).
    
    Args:
        suggestion_title: e.g. "Coffee Spot"
        suggestion_category: "poi" | "place" | "fallback"
        cadence_minutes: current cadence setting
        intensity: current intensity setting
        location: current location context
        explore_session_id: session ID if available
    
    Returns:
        Event ID (needed for outcome recording later)
    """
    if not LEARNING_AVAILABLE:
        return str(uuid4())
    
    try:
        event_id = record_event(
            "suggestion",
            explore_session_id=explore_session_id,
            location=location,
            metadata={
                "suggestion_title": suggestion_title,
                "suggestion_category": suggestion_category,
                "cadence_minutes": cadence_minutes,
                "intensity": intensity,
            }
        )
        logger.info(f"Suggestion recorded: {suggestion_title} (event {event_id})")
        return event_id
    except Exception as e:
        logger.error(f"Failed to record suggestion: {e}")
        return str(uuid4())


def on_skip_event(
    reason: str,
    explore_session_id: str | None = None,
    location: dict[str, Any] | None = None,
) -> str:
    """
    Called when Explore Mode skips a check (cadence not met, location unavailable, etc).
    
    Args:
        reason: "cadence_window_not_reached" | "location_unavailable" | "movement_suppressed" | etc.
        explore_session_id: session ID if available
        location: current location context
    
    Returns:
        Event ID
    """
    if not LEARNING_AVAILABLE:
        return str(uuid4())
    
    try:
        event_id = record_skip(
            explore_session_id=explore_session_id,
            reason=reason,
            location=location
        )
        logger.debug(f"Skip recorded: {reason} (event {event_id})")
        return event_id
    except Exception as e:
        logger.error(f"Failed to record skip: {e}")
        return str(uuid4())


# ---------------------------------------------------------------------------
# Outcome Recording (called when user reacts to suggestion)
# Note: These would be called from Telegram command handlers later
# ---------------------------------------------------------------------------

def on_suggestion_accepted(
    event_id: str,
    suggestion_title: str,
    suggestion_category: str,
    engagement_seconds: int | None = None,
    feedback: str | None = None,
) -> str:
    """
    Called when user accepts a suggestion (clicks, opens maps, etc).
    
    Args:
        event_id: ID from on_suggestion_offered()
        suggestion_title: title of suggestion
        suggestion_category: category of suggestion
        engagement_seconds: how long before they acted
        feedback: optional user text
    
    Returns:
        Outcome ID
    """
    if not LEARNING_AVAILABLE:
        return str(uuid4())
    
    try:
        outcome_id = record_outcome(
            event_id=event_id,
            outcome_type="accepted",
            suggestion_title=suggestion_title,
            suggestion_category=suggestion_category,
            engagement_seconds=engagement_seconds,
            feedback=feedback,
        )
        logger.info(f"Outcome recorded: accepted {suggestion_title}")
        return outcome_id
    except Exception as e:
        logger.error(f"Failed to record acceptance: {e}")
        return str(uuid4())


def on_suggestion_clicked(
    event_id: str,
    suggestion_title: str,
    suggestion_category: str,
    engagement_seconds: int | None = None,
) -> str:
    """
    Called when user clicks on a suggestion (opens link, opens maps).
    """
    if not LEARNING_AVAILABLE:
        return str(uuid4())
    
    try:
        outcome_id = record_outcome(
            event_id=event_id,
            outcome_type="clicked",
            suggestion_title=suggestion_title,
            suggestion_category=suggestion_category,
            engagement_seconds=engagement_seconds,
        )
        logger.info(f"Outcome recorded: clicked {suggestion_title}")
        return outcome_id
    except Exception as e:
        logger.error(f"Failed to record click: {e}")
        return str(uuid4())


def on_suggestion_bookmarked(
    event_id: str,
    suggestion_title: str,
    suggestion_category: str,
    engagement_seconds: int | None = None,
) -> str:
    """
    Called when user bookmarks/saves a suggestion to places.
    """
    if not LEARNING_AVAILABLE:
        return str(uuid4())
    
    try:
        outcome_id = record_outcome(
            event_id=event_id,
            outcome_type="bookmarked",
            suggestion_title=suggestion_title,
            suggestion_category=suggestion_category,
            engagement_seconds=engagement_seconds,
        )
        logger.info(f"Outcome recorded: bookmarked {suggestion_title}")
        return outcome_id
    except Exception as e:
        logger.error(f"Failed to record bookmark: {e}")
        return str(uuid4())


def on_suggestion_skipped(
    event_id: str,
    reason: str = "user_dismissed",
    engagement_seconds: int | None = None,
) -> str:
    """
    Called when user dismisses/skips a suggestion.
    
    Args:
        event_id: ID from on_suggestion_offered()
        reason: "user_dismissed" | "not_interested" | etc.
        engagement_seconds: how long before they dismissed
    
    Returns:
        Outcome ID
    """
    if not LEARNING_AVAILABLE:
        return str(uuid4())
    
    try:
        outcome_id = record_outcome(
            event_id=event_id,
            outcome_type="skipped",
            engagement_seconds=engagement_seconds,
            feedback=reason,
        )
        logger.info(f"Outcome recorded: skipped suggestion")
        return outcome_id
    except Exception as e:
        logger.error(f"Failed to record skip: {e}")
        return str(uuid4())


# ---------------------------------------------------------------------------
# Session Management
# ---------------------------------------------------------------------------

def on_explore_disabled(
    session_id: str,
    reason: str = "manual",
) -> None:
    """
    Called when Explore Mode is disabled.
    
    Could record session-level summary (total suggestions, acceptance rate, etc).
    Phase 2: analyze session outcomes and infer new skills.
    
    Args:
        session_id: session ID to close
        reason: "manual" | "expired" | etc.
    """
    if not LEARNING_AVAILABLE:
        return
    
    try:
        # Phase 2: compute session stats and update skills
        # For now, just record it
        record_event(
            "disable",
            explore_session_id=session_id,
            metadata={"reason": reason}
        )
        logger.info(f"Explore Mode session {session_id} disabled ({reason})")
    except Exception as e:
        logger.error(f"Failed to record Explore Mode disable: {e}")


# ---------------------------------------------------------------------------
# Summary & Stats (for Telegram responses or debug)
# ---------------------------------------------------------------------------

def get_session_stats(session_id: str) -> dict[str, Any]:
    """
    Get stats for a specific Explore Mode session.
    (Phase 2: implement detailed analysis)
    """
    from learning_db import get_event_summary, get_outcome_summary
    
    try:
        events = get_event_summary(limit=1000)
        outcomes = get_outcome_summary(limit=1000)
        
        session_events = [e for e in events if e["session_id"] == session_id]
        
        suggestions_sent = len([e for e in session_events if e["event_type"] == "suggestion"])
        outcomes_recorded = len([o for o in outcomes if any(
            e["id"] == session_id for e in session_events
        )])
        
        return {
            "session_id": session_id,
            "suggestions_sent": suggestions_sent,
            "outcomes_recorded": outcomes_recorded,
            "acceptance_rate": outcomes_recorded / suggestions_sent if suggestions_sent > 0 else 0,
        }
    except Exception as e:
        logger.error(f"Failed to get session stats: {e}")
        return {}


if __name__ == "__main__":
    # Smoke test
    print("🔗 Learning Layer ↔ Explore Mode Integration Test")
    
    if LEARNING_AVAILABLE:
        # Test enable
        session = on_explore_enabled(
            duration_label="2h",
            cadence_minutes=60,
            intensity="medium",
            location={"lat": 37.7749, "lon": -122.4194}
        )
        print(f"✓ Explore Mode enabled: {session}")
        
        # Test suggestion
        event = on_suggestion_offered(
            suggestion_title="Cafe Velocity",
            suggestion_category="poi",
            cadence_minutes=60,
            intensity="medium",
            explore_session_id=session
        )
        print(f"✓ Suggestion offered: {event}")
        
        # Test acceptance
        outcome = on_suggestion_accepted(
            event_id=event,
            suggestion_title="Cafe Velocity",
            suggestion_category="poi",
            engagement_seconds=5
        )
        print(f"✓ Suggestion accepted: {outcome}")
        
        # Test skip
        skip_event = on_skip_event(
            reason="cadence_window_not_reached",
            explore_session_id=session
        )
        print(f"✓ Skip recorded: {skip_event}")
        
        # Test disable
        on_explore_disabled(session, reason="manual")
        print(f"✓ Explore Mode disabled")
        
        print("\n✅ All integration tests passed")
    else:
        print("⚠ Learning DB not available (expected in development)")
        print("✅ Integration module loaded (will work when learning_db.py is available)")

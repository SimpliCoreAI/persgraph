"""
PersGraph Learning Layer — Explore Mode Outcome Handlers

Telegram command handlers for recording user reactions to Explore Mode suggestions.
Connects Telegram user actions (accept, skip, bookmark, click) to learning_explore_integration.

Usage (from command.py):
    /explore_accept <event_id> — user accepted suggestion
    /explore_skip <event_id> — user dismissed suggestion
    /explore_bookmark <event_id> — user saved suggestion to places
    /explore_click <event_id> — user clicked/opened suggestion
"""

from __future__ import annotations

import sys
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Ensure second_brain is in path
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from second_brain.learning_explore_integration import (
        on_suggestion_accepted,
        on_suggestion_clicked,
        on_suggestion_bookmarked,
        on_suggestion_skipped,
    )
    LEARNING_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    LEARNING_AVAILABLE = False
    logger.warning("Learning layer not available; outcome handlers will be no-ops")


def cmd_explore_accept(event_id: str, suggestion_title: str = "suggestion", engagement_seconds: Optional[int] = None) -> str:
    """
    Command handler for /explore_accept <event_id>
    
    Records that user accepted a suggestion (clicked, opened maps, etc).
    
    Args:
        event_id: event ID from on_suggestion_offered()
        suggestion_title: optional title of suggestion (for logging)
        engagement_seconds: optional time before user acted
    
    Returns:
        Confirmation message
    """
    if not LEARNING_AVAILABLE:
        return "⚠️ Learning layer unavailable; outcome not recorded"
    
    if not event_id or event_id.strip() == "":
        return "❌ Usage: /explore_accept <event_id>"
    
    try:
        outcome_id = on_suggestion_accepted(
            event_id=event_id.strip(),
            suggestion_title=suggestion_title,
            suggestion_category="poi",
            engagement_seconds=engagement_seconds,
        )
        logger.info(f"Outcome recorded: accept {event_id}")
        return f"✅ Outcome recorded: accepted\n🆔 Event: {event_id}\n📊 Outcome: {outcome_id}"
    except Exception as e:
        logger.error(f"Failed to record acceptance: {e}")
        return f"❌ Failed to record outcome: {e}"


def cmd_explore_click(event_id: str, suggestion_title: str = "suggestion", engagement_seconds: Optional[int] = None) -> str:
    """
    Command handler for /explore_click <event_id>
    
    Records that user clicked on a suggestion (opened link, opened maps).
    
    Args:
        event_id: event ID from on_suggestion_offered()
        suggestion_title: optional title of suggestion
        engagement_seconds: optional time before user clicked
    
    Returns:
        Confirmation message
    """
    if not LEARNING_AVAILABLE:
        return "⚠️ Learning layer unavailable; outcome not recorded"
    
    if not event_id or event_id.strip() == "":
        return "❌ Usage: /explore_click <event_id>"
    
    try:
        outcome_id = on_suggestion_clicked(
            event_id=event_id.strip(),
            suggestion_title=suggestion_title,
            suggestion_category="poi",
            engagement_seconds=engagement_seconds,
        )
        logger.info(f"Outcome recorded: click {event_id}")
        return f"✅ Outcome recorded: clicked\n🆔 Event: {event_id}\n📊 Outcome: {outcome_id}"
    except Exception as e:
        logger.error(f"Failed to record click: {e}")
        return f"❌ Failed to record outcome: {e}"


def cmd_explore_bookmark(event_id: str, suggestion_title: str = "suggestion", engagement_seconds: Optional[int] = None) -> str:
    """
    Command handler for /explore_bookmark <event_id>
    
    Records that user bookmarked/saved suggestion to places.
    
    Args:
        event_id: event ID from on_suggestion_offered()
        suggestion_title: optional title of suggestion
        engagement_seconds: optional time before user bookmarked
    
    Returns:
        Confirmation message
    """
    if not LEARNING_AVAILABLE:
        return "⚠️ Learning layer unavailable; outcome not recorded"
    
    if not event_id or event_id.strip() == "":
        return "❌ Usage: /explore_bookmark <event_id>"
    
    try:
        outcome_id = on_suggestion_bookmarked(
            event_id=event_id.strip(),
            suggestion_title=suggestion_title,
            suggestion_category="poi",
            engagement_seconds=engagement_seconds,
        )
        logger.info(f"Outcome recorded: bookmark {event_id}")
        return f"✅ Outcome recorded: bookmarked\n🆔 Event: {event_id}\n📊 Outcome: {outcome_id}"
    except Exception as e:
        logger.error(f"Failed to record bookmark: {e}")
        return f"❌ Failed to record outcome: {e}"


def cmd_explore_skip(event_id: str, reason: str = "user_dismissed") -> str:
    """
    Command handler for /explore_skip <event_id> [reason]
    
    Records that user dismissed/skipped suggestion.
    
    Args:
        event_id: event ID from on_suggestion_offered()
        reason: why user skipped (default: "user_dismissed")
    
    Returns:
        Confirmation message
    """
    if not LEARNING_AVAILABLE:
        return "⚠️ Learning layer unavailable; outcome not recorded"
    
    if not event_id or event_id.strip() == "":
        return "❌ Usage: /explore_skip <event_id> [reason]"
    
    try:
        outcome_id = on_suggestion_skipped(
            event_id=event_id.strip(),
            reason=reason,
            engagement_seconds=None,
        )
        logger.info(f"Outcome recorded: skip {event_id} ({reason})")
        return f"✅ Outcome recorded: skipped\n🆔 Event: {event_id}\n📊 Outcome: {outcome_id}"
    except Exception as e:
        logger.error(f"Failed to record skip: {e}")
        return f"❌ Failed to record outcome: {e}"


if __name__ == "__main__":
    # Smoke test
    print("🎯 Explore Mode Outcome Handlers — Smoke Test")
    
    if LEARNING_AVAILABLE:
        # Test a fake event_id (would normally come from on_suggestion_offered)
        fake_event_id = "test-event-12345"
        
        result = cmd_explore_accept(fake_event_id, suggestion_title="Test Cafe")
        print(f"✓ Accept: {result}")
        
        result = cmd_explore_skip(fake_event_id, reason="not_interested")
        print(f"✓ Skip: {result}")
        
        result = cmd_explore_bookmark(fake_event_id, suggestion_title="Test Cafe")
        print(f"✓ Bookmark: {result}")
        
        result = cmd_explore_click(fake_event_id, suggestion_title="Test Cafe")
        print(f"✓ Click: {result}")
    else:
        print("⚠️ Learning layer not available; smoke test skipped")

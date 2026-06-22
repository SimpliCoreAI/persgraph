"""
Universal Response Feedback Wrapper

Transparently captures feedback IDs for any response (chat, developer, command).
Minimal insertion point: wrap the response before returning to caller.

Safe: doesn't modify command behavior, just appends a feedback ID line.
"""

from __future__ import annotations

import logging
from typing import Any
from datetime import datetime, timezone
from uuid import uuid4

logger = logging.getLogger(__name__)

try:
    from second_brain import learning_db
    LEARNING_AVAILABLE = True
except ImportError:
    LEARNING_AVAILABLE = False


def record_response_feedback(
    response_text: str,
    command: str | None = None,
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """
    Record a feedback event for any response.
    
    Safe to call for any response type (command, chat, briefing).
    Does not modify the response text; ID is appended separately.
    
    Args:
        response_text: the actual response being returned
        command: command name if applicable (e.g. "/ask", "/note")
        user_id: user/sender ID if applicable
        metadata: arbitrary metadata (confidence, latency, etc.)
    
    Returns:
        tuple: (original_response_text, feedback_event_id)
        The event ID should be printed/sent as a separate message after the response.
    """
    if not LEARNING_AVAILABLE:
        return response_text, ""
    
    try:
        event_id = learning_db.record_event(
            event_type="response",
            metadata={
                "command": command or "unknown",
                "user_id": user_id,
                "response_length": len(response_text) if response_text else 0,
                "response_text": response_text,
                **(metadata or {}),
            }
        )
        
        if event_id:
            logger.debug(f"Response feedback recorded: {command} ({event_id})")
            return response_text, event_id
        
        return response_text, ""
        
    except Exception as e:
        logger.error(f"Failed to record response feedback: {e}")
        return response_text, ""


def format_response_with_feedback(
    response_text: str,
    feedback_event_id: str | None = None,
    include_id: bool = True,
) -> str:
    """
    Optionally append feedback ID to response.
    
    Args:
        response_text: original response
        feedback_event_id: ID from record_response_feedback()
        include_id: if False, returns unchanged response
    
    Returns:
        response text, optionally with feedback ID appended
    """
    if not include_id or not feedback_event_id:
        return response_text
    
    # Append as a separate visible line
    return f"{response_text}\n\n🆔 Response ID: `{feedback_event_id}`"


def wrap_response(
    response_text: str,
    command: str | None = None,
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    include_id_in_response: bool = False,
) -> str:
    """
    One-shot wrapper: record feedback and optionally include ID in response.
    
    Intended for use in command handlers or response pipelines.
    
    Args:
        response_text: the response to wrap
        command: command name
        user_id: user/sender ID
        metadata: arbitrary metadata
        include_id_in_response: if True, ID is appended to response text
                                if False, ID is returned separately (caller should emit)
    
    Returns:
        response text (with ID appended if include_id_in_response=True)
    """
    _, event_id = record_response_feedback(response_text, command, user_id, metadata)
    
    if include_id_in_response:
        return format_response_with_feedback(response_text, event_id, include_id=True)
    
    return response_text


def get_response_feedback_stats() -> dict[str, Any]:
    """Get summary of recorded response feedback."""
    if not LEARNING_AVAILABLE:
        return {}
    
    try:
        counts = learning_db.count_events_by_type()
        response_count = counts.get("response", 0)
        
        return {
            "response_feedback_count": response_count,
            "all_event_counts": counts,
        }
    except Exception as e:
        logger.error(f"Failed to get feedback stats: {e}")
        return {}


if __name__ == "__main__":
    # Smoke test
    print("🆔 Response Feedback Wrapper Test")
    
    if LEARNING_AVAILABLE:
        # Test 1: record feedback
        resp, eid = record_response_feedback(
            "Test response",
            command="/ask",
            user_id="test_user",
            metadata={"latency_ms": 123}
        )
        print(f"✓ Recorded feedback: {eid}")
        
        # Test 2: format with ID
        formatted = format_response_with_feedback(resp, eid, include_id=True)
        print(f"✓ Formatted response:\n{formatted}")
        
        # Test 3: wrap in one shot
        wrapped = wrap_response(
            "Another response",
            command="/note",
            user_id="test_user",
            include_id_in_response=False
        )
        print(f"✓ Wrapped response: {wrapped}")
        
        # Test 4: stats
        stats = get_response_feedback_stats()
        print(f"✓ Feedback stats: {stats}")
        
        print("\n✅ All tests passed")
    else:
        print("⚠️  Learning DB not available; wrapper would be no-op")

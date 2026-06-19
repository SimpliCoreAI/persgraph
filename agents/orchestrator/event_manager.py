"""
Event Manager — Event ID Generation & Feedback Loop Correlation

Provides:
  1. Generate unique event IDs for all significant actions
  2. Correlate feedback/result events back to original event ID
  3. Expose event ID in payloads so workers can attach it to outcomes
  4. Maintain bidirectional event→result mapping for audit trail

Usage:
    from agents.orchestrator.event_manager import generate_event_id, get_event_context

    event_id = generate_event_id("inbox_triage", "/note", user_id="12345")
    payload["event_id"] = event_id

    # Later, when result arrives:
    context = get_event_context(event_id)
    # Use to correlate, log audit entry, etc.
"""

import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

UTC = ZoneInfo("UTC")

# In-memory event registry: event_id → context
_EVENT_REGISTRY: dict[str, dict] = {}


def generate_event_id(
    worker_type: str,
    command: str,
    user_id: Optional[str] = None,
    timestamp: Optional[datetime] = None,
) -> str:
    """
    Generate a unique event ID for a routed action.

    Args:
        worker_type: The worker handling the action (e.g., "inbox_triage")
        command: The command being executed (e.g., "/note")
        user_id: The user initiating the action
        timestamp: When the action was created (defaults to now)

    Returns:
        A unique event ID string (e.g., "evt_abc123...")
    """
    if timestamp is None:
        timestamp = datetime.now(UTC)

    # Create a unique ID with timestamp + UUID for uniqueness
    uuid_part = str(uuid.uuid4())[:8]
    ts_part = timestamp.strftime("%Y%m%d%H%M%S")
    event_id = f"evt_{ts_part}_{uuid_part}"

    # Store in registry for later correlation
    _EVENT_REGISTRY[event_id] = {
        "event_id": event_id,
        "worker_type": worker_type,
        "command": command,
        "user_id": user_id,
        "created_at": timestamp.isoformat(),
        "status": "created",  # created → pending_approval → approved/rejected → executed → completed
        "approval_state": None,
        "result": None,
        "feedback_event_id": None,  # Event ID of the feedback/result event
    }

    return event_id


def get_event_context(event_id: str) -> Optional[dict]:
    """
    Retrieve the full context for an event.

    Args:
        event_id: The event ID to look up

    Returns:
        Dictionary with event metadata, or None if not found
    """
    return _EVENT_REGISTRY.get(event_id)


def update_event_status(
    event_id: str,
    status: str,
    approval_state: Optional[str] = None,
    result: Optional[str] = None,
) -> bool:
    """
    Update an event's status in the registry.

    Args:
        event_id: The event to update
        status: New status (created, pending_approval, approved, rejected, executed, completed)
        approval_state: Approval state if relevant (pending, approved, rejected, skipped)
        result: Result or outcome string

    Returns:
        True if updated, False if event not found
    """
    if event_id not in _EVENT_REGISTRY:
        return False

    ctx = _EVENT_REGISTRY[event_id]
    ctx["status"] = status
    if approval_state is not None:
        ctx["approval_state"] = approval_state
    if result is not None:
        ctx["result"] = result

    # Emit learning signal for status transitions
    # (deferred to callers who have full context; see learning_signals module)

    return True


def correlate_feedback_event(
    original_event_id: str,
    feedback_event_id: str,
) -> bool:
    """
    Link a feedback/result event to its original event.

    Args:
        original_event_id: The original action event ID
        feedback_event_id: The feedback/result event ID

    Returns:
        True if correlated, False if original event not found
    """
    if original_event_id not in _EVENT_REGISTRY:
        return False

    _EVENT_REGISTRY[original_event_id]["feedback_event_id"] = feedback_event_id
    return True


def list_events(
    status: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """
    List events from the registry with optional filtering.

    Args:
        status: Filter by status (e.g., "pending_approval")
        user_id: Filter by user ID
        limit: Maximum events to return

    Returns:
        List of event contexts
    """
    results = []
    for event_id, ctx in _EVENT_REGISTRY.items():
        if status and ctx["status"] != status:
            continue
        if user_id and ctx["user_id"] != user_id:
            continue
        results.append(ctx)

        if len(results) >= limit:
            break

    return results


def clear_event_registry() -> None:
    """
    Clear the entire event registry (use for testing only).
    """
    _EVENT_REGISTRY.clear()

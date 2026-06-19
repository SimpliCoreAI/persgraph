"""
Audit Logger — Append-Only Action & Outcome Record

Provides:
  1. Log action events (command, user, timestamp, event_id)
  2. Log outcome events (result, status, timestamp, event_id)
  3. Append-only JSON lines format for auditability
  4. Query audit trail by event_id, user_id, or date range
  5. Optional file persistence (default: in-memory for MVP)

Usage:
    from agents.orchestrator.audit_logger import log_action, log_outcome, read_audit_trail

    log_action(event_id, user_id, command, args, worker_type)
    # ... execute action ...
    log_outcome(event_id, status, result, worker_type)

    # Query:
    trail = read_audit_trail(event_id=event_id)
    all_user_actions = read_audit_trail(user_id=user_id)
"""

import json
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Optional
from enum import Enum

UTC = ZoneInfo("UTC")

# In-memory audit trail (list of log entries)
_AUDIT_TRAIL: list[dict] = []

# Optional file path for persistence
_AUDIT_LOG_FILE: Optional[Path] = None


class EventType(Enum):
    """Types of audit events."""
    ACTION_CREATED = "action_created"
    ACTION_ROUTED = "action_routed"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    ACTION_EXECUTED = "action_executed"
    ACTION_COMPLETED = "action_completed"
    ACTION_FAILED = "action_failed"
    FEEDBACK_RECEIVED = "feedback_received"


def set_audit_log_file(file_path: Path | str) -> None:
    """
    Set the file path for audit trail persistence.

    Args:
        file_path: Path to append-only audit log file
    """
    global _AUDIT_LOG_FILE
    _AUDIT_LOG_FILE = Path(file_path)


def log_action(
    event_id: str,
    user_id: Optional[str],
    command: str,
    args: str,
    worker_type: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    """
    Log an action event.

    Args:
        event_id: Unique event ID for this action
        user_id: User who initiated the action
        command: Command being executed (e.g., "/note")
        args: Command arguments
        worker_type: Which worker handles it (or None if routed to orchestrator)
        metadata: Optional extra metadata (e.g., approval required, reason)
    """
    entry = {
        "event_type": EventType.ACTION_CREATED.value,
        "event_id": event_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "user_id": user_id,
        "command": command,
        "args": args,
        "worker_type": worker_type,
        "metadata": metadata or {},
    }

    _append_entry(entry)


def log_approval_request(
    event_id: str,
    command: str,
    reason: str,
    requested_by: Optional[str] = None,
) -> None:
    """
    Log that an action has been marked for approval.

    Args:
        event_id: Event ID of the action
        command: The command
        reason: Why approval is needed
        requested_by: Who requested the approval
    """
    entry = {
        "event_type": EventType.APPROVAL_REQUESTED.value,
        "event_id": event_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "command": command,
        "reason": reason,
        "requested_by": requested_by,
    }

    _append_entry(entry)


def log_approval_decision(
    event_id: str,
    decision: str,  # "approved" or "rejected"
    decided_by: str,
    reason: Optional[str] = None,
) -> None:
    """
    Log an approval decision.

    Args:
        event_id: Event ID of the action
        decision: "approved" or "rejected"
        decided_by: Who made the decision
        reason: Optional reason
    """
    event_type = (
        EventType.APPROVAL_GRANTED.value
        if decision.lower() == "approved"
        else EventType.APPROVAL_DENIED.value
    )

    entry = {
        "event_type": event_type,
        "event_id": event_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "decision": decision,
        "decided_by": decided_by,
        "reason": reason,
    }

    _append_entry(entry)


def log_execution(
    event_id: str,
    worker_type: Optional[str],
    status: str = "executing",
) -> None:
    """
    Log that an action has started execution.

    Args:
        event_id: Event ID of the action
        worker_type: Which worker is executing
        status: "executing", "executed", etc.
    """
    entry = {
        "event_type": EventType.ACTION_EXECUTED.value,
        "event_id": event_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "worker_type": worker_type,
        "status": status,
    }

    _append_entry(entry)


def log_outcome(
    event_id: str,
    status: str,  # "completed", "failed", etc.
    result: str,
    worker_type: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    """
    Log the outcome of an action.

    Args:
        event_id: Event ID of the action
        status: Outcome status ("completed", "failed", "cancelled", etc.)
        result: Result or output string
        worker_type: Which worker produced the result
        error: Error message if failed
    """
    event_type = (
        EventType.ACTION_COMPLETED.value
        if status == "completed"
        else EventType.ACTION_FAILED.value
    )

    entry = {
        "event_type": event_type,
        "event_id": event_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "status": status,
        "result": result,
        "worker_type": worker_type,
        "error": error,
    }

    _append_entry(entry)


def log_feedback(
    event_id: str,
    feedback_event_id: str,
    feedback_data: dict,
) -> None:
    """
    Log feedback or result event correlated to an original action.

    Args:
        event_id: Original event ID
        feedback_event_id: Feedback event ID
        feedback_data: Feedback payload
    """
    entry = {
        "event_type": EventType.FEEDBACK_RECEIVED.value,
        "event_id": event_id,
        "feedback_event_id": feedback_event_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "feedback_data": feedback_data,
    }

    _append_entry(entry)


def read_audit_trail(
    event_id: Optional[str] = None,
    user_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 1000,
) -> list[dict]:
    """
    Query the audit trail.

    Args:
        event_id: Filter by event ID
        user_id: Filter by user ID
        event_type: Filter by event type
        limit: Maximum results to return

    Returns:
        List of matching audit entries
    """
    results = []

    for entry in _AUDIT_TRAIL:
        if event_id and entry.get("event_id") != event_id:
            continue
        if user_id and entry.get("user_id") != user_id:
            continue
        if event_type and entry.get("event_type") != event_type:
            continue

        results.append(entry)

        if len(results) >= limit:
            break

    return results


def _append_entry(entry: dict) -> None:
    """
    Append an entry to the audit trail and optionally to file.

    Args:
        entry: Dictionary to append
    """
    _AUDIT_TRAIL.append(entry)

    # Persist to file if configured
    if _AUDIT_LOG_FILE:
        try:
            _AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(_AUDIT_LOG_FILE, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            # Log to stderr but don't fail the action
            import sys
            print(f"[AUDIT LOG ERROR] Failed to write audit log: {e}", file=sys.stderr)


def clear_audit_trail() -> None:
    """
    Clear the in-memory audit trail (use for testing only).
    """
    _AUDIT_TRAIL.clear()


def get_audit_trail_size() -> int:
    """
    Return the number of entries in the audit trail.

    Returns:
        Count of audit entries
    """
    return len(_AUDIT_TRAIL)


def export_audit_trail(file_path: Path | str) -> int:
    """
    Export the entire in-memory audit trail to a file.

    Args:
        file_path: Path to write the trail to

    Returns:
        Number of entries exported
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w") as f:
        for entry in _AUDIT_TRAIL:
            f.write(json.dumps(entry) + "\n")

    return len(_AUDIT_TRAIL)

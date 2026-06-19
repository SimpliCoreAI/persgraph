"""
Approval Gate — Human-in-the-Loop Decision Points

Provides:
  1. Mark actions as pending approval
  2. List approval-pending actions for a user/admin
  3. Approve or reject an action
  4. Skip approval for low-risk actions
  5. Track approval decision + timeline in audit trail

Usage:
    from agents.orchestrator.approval_gate import (
        mark_for_approval, approve_action, reject_action, 
        list_pending_approvals, skip_approval
    )

    # On initial routing:
    if is_high_impact(command, args):
        event_id = mark_for_approval(event_id, command, args, reason)
        return "⏸️ Action pending approval"

    # Admin checks pending actions:
    pending = list_pending_approvals(user_id="admin")

    # Admin approves:
    approve_action(event_id, approved_by="admin")
    # Then proceed to execute_action()

    # Admin rejects:
    reject_action(event_id, reason="Too risky", rejected_by="admin")
"""

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional
from enum import Enum

from agents.orchestrator.event_manager import (
    get_event_context,
    update_event_status,
)

UTC = ZoneInfo("UTC")


class ApprovalState(Enum):
    """Approval decision states."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SKIPPED = "skipped"


# In-memory approval registry: event_id → approval decision
_APPROVAL_REGISTRY: dict[str, dict] = {}


def mark_for_approval(
    event_id: str,
    command: str,
    args: str,
    reason: str = "",
    requires_human: bool = True,
) -> bool:
    """
    Mark an event as requiring approval before execution.

    Args:
        event_id: The event ID to mark
        command: The command being executed
        args: The command arguments
        reason: Why this action requires approval
        requires_human: If True, a human must approve; if False, auto-approve after delay

    Returns:
        True if marked, False if already in registry
    """
    if event_id in _APPROVAL_REGISTRY:
        return False

    ctx = get_event_context(event_id)
    if not ctx:
        return False

    _APPROVAL_REGISTRY[event_id] = {
        "event_id": event_id,
        "command": command,
        "args": args,
        "reason": reason,
        "requires_human": requires_human,
        "state": ApprovalState.PENDING.value,
        "requested_at": datetime.now(UTC).isoformat(),
        "decided_at": None,
        "decided_by": None,
        "decision_reason": None,
    }

    # Update event status
    update_event_status(event_id, "pending_approval", approval_state="pending")

    return True


def approve_action(
    event_id: str,
    approved_by: str = "system",
    reason: str = "",
) -> bool:
    """
    Approve a pending action.

    Args:
        event_id: The event to approve
        approved_by: Who approved (username, admin ID, etc.)
        reason: Optional reason for approval

    Returns:
        True if approved, False if not pending
    """
    if event_id not in _APPROVAL_REGISTRY:
        return False

    approval = _APPROVAL_REGISTRY[event_id]
    if approval["state"] != ApprovalState.PENDING.value:
        return False

    approval["state"] = ApprovalState.APPROVED.value
    approval["decided_at"] = datetime.now(UTC).isoformat()
    approval["decided_by"] = approved_by
    approval["decision_reason"] = reason

    # Update event status
    update_event_status(event_id, "approved", approval_state="approved")

    # Emit learning signal for approval decision
    try:
        from agents.orchestrator.learning_signals import emit_approval_signal
        emit_approval_signal(
            event_id=event_id,
            command=approval.get("command", "unknown"),
            decision="approved",
            confidence=1.0,
            decided_by=approved_by,
            reason=reason,
        )
    except Exception:
        pass  # Learning signals not critical

    return True


def reject_action(
    event_id: str,
    reason: str = "",
    rejected_by: str = "system",
) -> bool:
    """
    Reject a pending action.

    Args:
        event_id: The event to reject
        reason: Why the action was rejected
        rejected_by: Who rejected (username, admin ID, etc.)

    Returns:
        True if rejected, False if not pending
    """
    if event_id not in _APPROVAL_REGISTRY:
        return False

    approval = _APPROVAL_REGISTRY[event_id]
    if approval["state"] != ApprovalState.PENDING.value:
        return False

    approval["state"] = ApprovalState.REJECTED.value
    approval["decided_at"] = datetime.now(UTC).isoformat()
    approval["decided_by"] = rejected_by
    approval["decision_reason"] = reason

    # Update event status
    update_event_status(event_id, "rejected", approval_state="rejected")

    # Emit learning signal for rejection decision
    try:
        from agents.orchestrator.learning_signals import emit_approval_signal
        emit_approval_signal(
            event_id=event_id,
            command=approval.get("command", "unknown"),
            decision="rejected",
            confidence=1.0,
            decided_by=rejected_by,
            reason=reason,
        )
    except Exception:
        pass  # Learning signals not critical

    return True


def skip_approval(
    event_id: str,
    reason: str = "Low-risk action",
) -> bool:
    """
    Skip approval for a low-risk action.

    Args:
        event_id: The event to skip approval for
        reason: Why approval is skipped

    Returns:
        True if skipped, False if already in registry
    """
    if event_id in _APPROVAL_REGISTRY:
        return False

    _APPROVAL_REGISTRY[event_id] = {
        "event_id": event_id,
        "command": None,
        "args": None,
        "reason": reason,
        "requires_human": False,
        "state": ApprovalState.SKIPPED.value,
        "requested_at": datetime.now(UTC).isoformat(),
        "decided_at": datetime.now(UTC).isoformat(),
        "decided_by": "system",
        "decision_reason": reason,
    }

    # Update event status
    update_event_status(event_id, "approved", approval_state="skipped")

    # Emit learning signal for skipped approval
    try:
        from agents.orchestrator.learning_signals import emit_approval_signal
        ctx = get_event_context(event_id)
        emit_approval_signal(
            event_id=event_id,
            command=ctx.get("command", "unknown") if ctx else "unknown",
            decision="skipped",
            confidence=1.0,
            decided_by="system",
            reason=reason,
        )
    except Exception:
        pass  # Learning signals not critical

    return True


def get_approval_status(event_id: str) -> Optional[dict]:
    """
    Get the approval status for an event.

    Args:
        event_id: The event to check

    Returns:
        Approval dictionary or None if not found
    """
    return _APPROVAL_REGISTRY.get(event_id)


def is_approved(event_id: str) -> bool:
    """
    Check if an event has been approved.

    Args:
        event_id: The event to check

    Returns:
        True if approved or skipped, False otherwise
    """
    approval = get_approval_status(event_id)
    if not approval:
        return False

    state = approval["state"]
    return state in (ApprovalState.APPROVED.value, ApprovalState.SKIPPED.value)


def is_rejected(event_id: str) -> bool:
    """
    Check if an event has been rejected.

    Args:
        event_id: The event to check

    Returns:
        True if rejected, False otherwise
    """
    approval = get_approval_status(event_id)
    if not approval:
        return False

    return approval["state"] == ApprovalState.REJECTED.value


def list_pending_approvals(
    requires_human: bool = True,
    limit: int = 50,
) -> list[dict]:
    """
    List all pending approval requests.

    Args:
        requires_human: Filter by requires_human flag
        limit: Maximum to return

    Returns:
        List of pending approvals
    """
    results = []
    for event_id, approval in _APPROVAL_REGISTRY.items():
        if approval["state"] != ApprovalState.PENDING.value:
            continue
        if requires_human and not approval["requires_human"]:
            continue

        results.append(approval)
        if len(results) >= limit:
            break

    return results


def clear_approval_registry() -> None:
    """
    Clear the entire approval registry (use for testing only).
    """
    _APPROVAL_REGISTRY.clear()

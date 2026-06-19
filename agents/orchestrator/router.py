"""
PersGraph Command Router

Routes incoming commands to the appropriate worker type based on the command
and enforces tool/scope boundaries. Part of the MVP orchestration layer.

Includes event ID generation, approval gating, and audit trail integration.

Usage:
    from agents.orchestrator.router import route_command_with_gates

    routed_task = route_command_with_gates("/note buy groceries", user_context)
    if routed_task.requires_approval:
        return f"⏸️ Approval pending: {routed_task.event_id}"
    # Otherwise proceed to execute worker
"""

from typing import NamedTuple
from agents.orchestrator.worker_registry import (
    WorkerType,
    get_worker_for_command,
    get_capabilities,
    enforce_capability,
)
from agents.orchestrator.event_manager import generate_event_id
from agents.orchestrator.approval_gate import skip_approval
from agents.orchestrator.audit_logger import log_action


class RoutedTask(NamedTuple):
    """Represents a routed task with worker assignment and payload."""
    event_id: str  # Unique event ID for this action
    worker_type: WorkerType | None
    command: str
    args: str
    payload: dict  # Task-specific metadata (includes event_id)
    user_context: dict  # User info (name, tier, model, etc.)
    bypass_worker: bool  # True if orchestrator handles directly
    requires_approval: bool  # True if action needs human approval
    approval_reason: str | None  # Why approval is needed


def route_command(raw_input: str, user_context: dict | None = None) -> RoutedTask:
    """
    Route a command to the appropriate worker.

    Args:
        raw_input: Full command string, e.g., "/note buy groceries"
        user_context: User metadata (id, tier, model, name, etc.)

    Returns:
        RoutedTask with worker assignment, payload, and routing hints.
    """
    if user_context is None:
        user_context = {"name": "guest", "tier": "guest"}

    # Extract command and args
    parts = raw_input.strip().split(None, 1)
    if not parts:
        empty_event_id = generate_event_id(
            "orchestrator",
            "",
            user_id=user_context.get("id"),
        )
        return RoutedTask(
            event_id=empty_event_id,
            worker_type=None,
            command="",
            args="",
            payload={"event_id": empty_event_id},
            user_context=user_context,
            bypass_worker=True,
            requires_approval=False,
            approval_reason=None,
        )

    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    # Look up worker for this command
    worker_type = get_worker_for_command(command)

    # Generate event ID for this action
    event_id = generate_event_id(
        worker_type.value if worker_type else "orchestrator",
        command,
        user_id=user_context.get("id"),
    )

    # Determine if we bypass to orchestrator (no dedicated worker)
    bypass_worker = worker_type is None

    # Build payload with common metadata (includes event_id)
    payload = {
        "event_id": event_id,
        "command": command,
        "args": args,
        "user_tier": user_context.get("tier", "guest"),
        "user_id": user_context.get("id", "unknown"),
        "user_name": user_context.get("name", "guest"),
        "timestamp": None,  # Set by worker if needed
    }

    # Determine if approval is needed (MVP: no commands require approval by default)
    requires_approval = False
    approval_reason = None

    # Log the action to audit trail
    log_action(
        event_id,
        user_context.get("id"),
        command,
        args,
        worker_type=worker_type.value if worker_type else "orchestrator",
    )

    # Emit routing signal for learning layer
    try:
        from agents.orchestrator.learning_signals import emit_routing_signal
        emit_routing_signal(
            event_id=event_id,
            worker_type=worker_type.value if worker_type else None,
            command=command,
            user_tier=user_context.get("tier", "guest"),
            confidence=1.0,
            reason="Routed via route_command",
        )
    except Exception:
        pass  # Learning signals not critical

    return RoutedTask(
        event_id=event_id,
        worker_type=worker_type,
        command=command,
        args=args,
        payload=payload,
        user_context=user_context,
        bypass_worker=bypass_worker,
        requires_approval=requires_approval,
        approval_reason=approval_reason,
    )


def route_command_with_gates(
    raw_input: str,
    user_context: dict | None = None,
) -> RoutedTask:
    """
    Route a command with approval gates applied.

    Handles:
      1. Event ID generation
      2. Approval marking for high-impact actions
      3. Audit logging

    Args:
        raw_input: Full command string
        user_context: User metadata

    Returns:
        RoutedTask with approval gates already evaluated
    """
    routed = route_command(raw_input, user_context)

    # For MVP, no commands require approval by default
    # Future: implement policy-based approval (e.g., /ingest external URLs, /task delete)
    # if routed.requires_approval:
    #     mark_for_approval(...)
    # else:
    skip_approval(routed.event_id, reason="Low-risk action (MVP)")

    return routed


def validate_worker_access(worker_type: WorkerType, required_tools: list[str]) -> tuple[bool, list[str]]:
    """
    Validate that a worker has access to all required tools.

    Args:
        worker_type: The worker type to validate
        required_tools: List of tools the worker wants to use

    Returns:
        (is_allowed: bool, denied_tools: list[str])
    """
    denied = []
    for tool in required_tools:
        if not enforce_capability(worker_type, tool):
            denied.append(tool)

    return len(denied) == 0, denied


def get_worker_entrypoint(worker_type: WorkerType) -> str | None:
    """
    Return the module path for a worker type's entrypoint.
    Used to dynamically import and call the worker.

    Returns:
        Module path string or None if no direct entrypoint.
    """
    entrypoints = {
        WorkerType.INBOX_TRIAGE: "agents.inbox_triage.worker.run",
        WorkerType.CALENDAR_PREP: "agents.calendar_prep.worker.run",
        WorkerType.TRAVEL_SCOUT: "agents.travel_scout_worker.worker.run",
        WorkerType.INGEST: "agents.ingest_worker_mvp.worker.run",
        WorkerType.DEBRIEF: "agents.debrief_worker.worker.run",
    }
    return entrypoints.get(worker_type)


def summarize_routing(routed_task: RoutedTask) -> dict:
    """
    Return a summary of the routing decision for logging/debugging.

    Args:
        routed_task: RoutedTask from route_command()

    Returns:
        Dictionary with routing info.
    """
    return {
        "event_id": routed_task.event_id,
        "command": routed_task.command,
        "worker_type": routed_task.worker_type.value if routed_task.worker_type else None,
        "bypass_worker": routed_task.bypass_worker,
        "requires_approval": routed_task.requires_approval,
        "user_tier": routed_task.user_context.get("tier"),
        "tools_scope": (
            list(get_capabilities(routed_task.worker_type).allowed_tools)
            if routed_task.worker_type
            else []
        ),
    }

"""
PersGraph Command Router

Routes incoming commands to the appropriate worker type based on the command
and enforces tool/scope boundaries. Part of the MVP orchestration layer.

Usage:
    from agents.orchestrator.router import route_command

    worker_type, task_payload = route_command("/note buy groceries", user_context)
    if worker_type:
        # dispatch to worker with task_payload
        execute_worker(worker_type, task_payload)
"""

from typing import NamedTuple
from agents.orchestrator.worker_registry import (
    WorkerType,
    get_worker_for_command,
    get_capabilities,
    enforce_capability,
)


class RoutedTask(NamedTuple):
    """Represents a routed task with worker assignment and payload."""
    worker_type: WorkerType | None
    command: str
    args: str
    payload: dict  # Task-specific metadata
    user_context: dict  # User info (name, tier, model, etc.)
    bypass_worker: bool  # True if orchestrator handles directly


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
        return RoutedTask(
            worker_type=None,
            command="",
            args="",
            payload={},
            user_context=user_context,
            bypass_worker=True,
        )

    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    # Look up worker for this command
    worker_type = get_worker_for_command(command)

    # Build payload with common metadata
    payload = {
        "command": command,
        "args": args,
        "user_tier": user_context.get("tier", "guest"),
        "user_id": user_context.get("id", "unknown"),
        "user_name": user_context.get("name", "guest"),
        "timestamp": None,  # Set by worker if needed
    }

    # Determine if we bypass to orchestrator (no dedicated worker)
    bypass_worker = worker_type is None

    return RoutedTask(
        worker_type=worker_type,
        command=command,
        args=args,
        payload=payload,
        user_context=user_context,
        bypass_worker=bypass_worker,
    )


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
        "command": routed_task.command,
        "worker_type": routed_task.worker_type.value if routed_task.worker_type else None,
        "bypass_worker": routed_task.bypass_worker,
        "user_tier": routed_task.user_context.get("tier"),
        "tools_scope": (
            list(get_capabilities(routed_task.worker_type).allowed_tools)
            if routed_task.worker_type
            else []
        ),
    }

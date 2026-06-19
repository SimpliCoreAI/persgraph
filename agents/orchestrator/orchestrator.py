"""
PersGraph Orchestrator — Main Dispatcher

Integrates the router and worker registry with the existing command_handler.
This is the entry point for commands when using the routing layer.

Backward Compatibility:
  - Direct command_handler.run() still works (existing entrypoints)
  - orchestrator.run_with_routing() uses the new routing layer (opt-in)
  - Both paths end at the same command handlers

Routing Layer Features:
  - Event ID generation for all actions
  - Approval gates for high-impact actions
  - Audit trail tracking
  - Feedback loop correlation

Usage:
    from agents.orchestrator.orchestrator import run_with_routing

    result = run_with_routing("/note buy groceries", sender_id="12345")
    # Returns: result with routing metadata appended if ENV[ROUTING_DEBUG]=1
"""

import os
import sys

from agents.orchestrator.router import route_command_with_gates, summarize_routing
from agents.orchestrator.audit_logger import log_execution, log_outcome


def run_with_routing(raw_input: str, sender_id: str | None = None) -> str:
    """
    Dispatch a command using the routing layer with event tracking and approval gates.

    For now, this is a thin wrapper that:
      1. Routes the command via route_command_with_gates()
      2. Checks approval gates
      3. Logs execution
      4. Falls back to existing command_handler for actual execution
      5. Logs outcome

    In future iterations, will actually spawn worker processes.

    Args:
        raw_input: Full command string
        sender_id: Optional Telegram sender ID

    Returns:
        Command result string
    """
    # Import command_handler for the actual execution
    from agents.orchestrator import command_handler

    # Resolve user context
    user = command_handler.resolve_user(sender_id)

    # Route the command with approval gates
    routed_task = route_command_with_gates(raw_input, user_context=user)

    # Log routing if DEBUG is enabled
    if os.environ.get("ROUTING_DEBUG"):
        routing_info = summarize_routing(routed_task)
        print(f"[ROUTING] {routing_info}", file=sys.stderr)

    # Check approval gates
    if routed_task.requires_approval:
        return f"⏸️ Action pending approval (event_id: {routed_task.event_id})"

    # Log execution start
    log_execution(
        routed_task.event_id,
        routed_task.worker_type.value if routed_task.worker_type else "orchestrator",
        status="executing",
    )

    # For MVP, still dispatch to existing command_handler
    # Future: actually invoke the routed worker
    try:
        import time
        start_ms = int(time.time() * 1000)
        result = command_handler.run(raw_input, sender_id)
        duration_ms = int(time.time() * 1000) - start_ms
        
        # Log outcome (success)
        log_outcome(
            routed_task.event_id,
            "completed",
            result,
            worker_type=routed_task.worker_type.value if routed_task.worker_type else "orchestrator",
        )
        
        # Emit outcome signal for learning layer
        try:
            from agents.orchestrator.learning_signals import emit_outcome_signal
            result_preview = result[:100] if result else ""
            emit_outcome_signal(
                event_id=routed_task.event_id,
                command=routed_task.command,
                worker_type=routed_task.worker_type.value if routed_task.worker_type else "orchestrator",
                status="completed",
                success=True,
                duration_ms=duration_ms,
                result_preview=result_preview,
            )
        except Exception:
            pass  # Learning signals not critical
        
        return result
    except Exception as e:
        # Log outcome (failure)
        error_msg = str(e)
        log_outcome(
            routed_task.event_id,
            "failed",
            error_msg,
            worker_type=routed_task.worker_type.value if routed_task.worker_type else "orchestrator",
            error=error_msg,
        )
        
        # Emit outcome signal for learning layer (failure)
        try:
            from agents.orchestrator.learning_signals import emit_outcome_signal
            emit_outcome_signal(
                event_id=routed_task.event_id,
                command=routed_task.command,
                worker_type=routed_task.worker_type.value if routed_task.worker_type else "orchestrator",
                status="failed",
                success=False,
                duration_ms=0,
                error=error_msg,
            )
        except Exception:
            pass  # Learning signals not critical
        
        raise


def describe_routing() -> dict:
    """
    Return a description of the routing layer for introspection/testing.

    Returns:
        Dict with command→worker mappings and worker capabilities.
    """
    from agents.orchestrator.worker_registry import list_workers, describe_worker
    from agents.orchestrator.worker_registry import get_worker_for_command

    routing_map = {}
    for cmd in [
        "/note", "/task", "/place", "/places", "/bucketlist",
        "/appointment", "/schedule",
        "/triptoggle", "/explore_accept", "/explore_click", "/explore_skip", "/explore_bookmark",
        "/ingest", "/wiki-ingest",
        "/digest", "/debrief",
        "/ask", "/email", "/sport", "/pghelp", "/status"
    ]:
        worker = get_worker_for_command(cmd)
        if worker:
            routing_map[cmd] = worker.value
        else:
            routing_map[cmd] = "orchestrator"

    workers_info = {
        worker.value: describe_worker(worker)
        for worker in list_workers()
    }

    return {
        "routing_table": routing_map,
        "workers": workers_info,
    }


def get_event_registry_snapshot() -> dict:
    """
    Return a snapshot of the event registry (for debugging/introspection).

    Returns:
        Dict with current event state.
    """
    from agents.orchestrator.event_manager import list_events
    from agents.orchestrator.approval_gate import list_pending_approvals

    return {
        "total_events": len(list_events(limit=10000)),
        "pending_approvals": list_pending_approvals(limit=50),
        "recent_events": list_events(limit=10),
    }

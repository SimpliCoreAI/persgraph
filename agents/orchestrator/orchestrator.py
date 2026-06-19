"""
PersGraph Orchestrator — Main Dispatcher

Integrates the router and worker registry with the existing command_handler.
This is the entry point for commands when using the routing layer.

Backward Compatibility:
  - Direct command_handler.run() still works (existing entrypoints)
  - orchestrator.run() uses the new routing layer (opt-in)
  - Both paths end at the same command handlers

Usage:
    from agents.orchestrator.orchestrator import run_with_routing

    result = run_with_routing("/note buy groceries", sender_id="12345")
    # Returns: result with routing metadata appended if ENV[ROUTING_DEBUG]=1
"""

import os
import sys

from agents.orchestrator.router import route_command, summarize_routing
from agents.orchestrator.worker_registry import get_worker_for_command


def run_with_routing(raw_input: str, sender_id: str | None = None) -> str:
    """
    Dispatch a command using the routing layer.

    For now, this is a thin wrapper that:
      1. Routes the command via route_command()
      2. Logs the routing decision (if DEBUG enabled)
      3. Falls back to existing command_handler for actual execution

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

    # Route the command
    routed_task = route_command(raw_input, user_context=user)

    # Log routing if DEBUG is enabled
    if os.environ.get("ROUTING_DEBUG"):
        routing_info = summarize_routing(routed_task)
        print(f"[ROUTING] {routing_info}", file=sys.stderr)

    # For MVP, still dispatch to existing command_handler
    # Future: actually invoke the routed worker
    result = command_handler.run(raw_input, sender_id)

    return result


def describe_routing() -> dict:
    """
    Return a description of the routing layer for introspection/testing.

    Returns:
        Dict with command→worker mappings and worker capabilities.
    """
    from agents.orchestrator.worker_registry import list_workers, describe_worker

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

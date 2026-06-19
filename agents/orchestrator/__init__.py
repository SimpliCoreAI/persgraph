"""
PersGraph Orchestrator

This package contains the top-level command routing and orchestration logic.

Modules:
  - command_handler: Telegram command dispatcher (/ask, /ingest, /note, /place, etc.)
  - query_handler: Search/query orchestrator (retrieves context, generates answers)
  - server: Flask web server serving dashboards and tools
  - event_manager: Event ID generation & tracking for audit trail
  - approval_gate: Human-in-the-loop approval decisions
  - audit_logger: Append-only action & outcome record
  - router: Command → worker routing with event/approval integration
  - orchestrator: Main dispatcher using routing layer
  - worker_registry: Worker type definitions and capabilities
  - learning_signals: Bridge between orchestrator events and learning layer
  - worker_refinement: Signal consumer for router/worker improvements

The wrappers in scripts/ and root server.py delegate to this module for backward compatibility.

Each orchestrator module dispatches to specialized workers in agents/<domain>/ or
invokes shared libraries in second_brain/ (ingesters, query engines, etc.).
"""

__all__ = [
    "command_handler",
    "query_handler",
    "server",
    "event_manager",
    "approval_gate",
    "audit_logger",
    "router",
    "orchestrator",
    "worker_registry",
    "learning_signals",
    "worker_refinement",
]

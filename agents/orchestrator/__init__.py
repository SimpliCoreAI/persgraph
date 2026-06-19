"""
PersGraph Orchestrator

This package contains the top-level command routing and orchestration logic.

Modules:
  - command_handler: Telegram command dispatcher (/ask, /ingest, /note, /place, etc.)
  - query_handler: Search/query orchestrator (retrieves context, generates answers)
  - server: Flask web server serving dashboards and tools

The wrappers in scripts/ and root server.py delegate to this module for backward compatibility.

Each orchestrator module dispatches to specialized workers in agents/<domain>/ or
invokes shared libraries in second_brain/ (ingesters, query engines, etc.).
"""

__all__ = ["command_handler", "query_handler", "server"]

"""
PersGraph Runtime Infrastructure

This package contains the async execution layer and queue management for PersGraph.

Modules:
  - queue_worker: Async task processor (cron-driven)
  - server: Flask web server for UI and dashboards
  - query_handler: Query orchestrator for the search/answer flow

Data:
  - queue.json lives in data/ (see second_brain/queue.py for path)

The wrappers in scripts/ delegate to this module for backward compatibility.
"""

__all__ = ["queue_worker", "server", "query_handler"]

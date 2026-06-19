"""
Ingest Worker (MVP stub)

Handles /ingest, /wiki-ingest commands.
Restricted to chroma, ollama, url_fetcher, wikipedia, docs_storage tools.

Currently delegates to existing ingest handlers.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.orchestrator.worker_base import BaseWorker
from agents.orchestrator.worker_registry import WorkerType


class IngestWorker(BaseWorker):
    """Handles knowledge ingestion."""

    def __init__(self):
        super().__init__(WorkerType.INGEST)

    def execute(self, payload: dict) -> str:
        """
        Execute an ingest command.

        payload includes:
          - command: "/ingest" or "/wiki-ingest"
          - args: the URL
          - user_tier: for model selection
        """
        command = payload.get("command", "").lower()
        args = payload.get("args", "")
        user = payload.get("user_context", {})

        try:
            from agents.orchestrator import command_handler
        except ImportError as e:
            return f"❌ Failed to import command handlers: {e}"

        handlers = {
            "/ingest": command_handler.cmd_ingest,
            "/wiki-ingest": command_handler.cmd_wiki_ingest,
            "/wiki_ingest": command_handler.cmd_wiki_ingest,
        }

        handler = handlers.get(command)
        if not handler:
            return f"❌ Unknown ingest command: {command}"

        try:
            # Some handlers accept user context
            if command in ["/ingest"]:
                result = handler(args, user=user)
            else:
                result = handler(args)
            return result
        except Exception as e:
            return f"❌ Ingest error: {str(e)}"


def run(routed_task) -> str:
    """Entrypoint for the ingest worker."""
    worker = IngestWorker()
    return worker.run(routed_task)

"""
Debrief Worker (MVP stub)

Handles /digest and /debrief commands.
Restricted to chroma, llm, and read-only DB access.

Currently delegates to existing digest/debrief handlers.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.orchestrator.worker_base import BaseWorker
from agents.orchestrator.worker_registry import WorkerType


class DebriefWorker(BaseWorker):
    """Handles digest and debrief generation."""

    def __init__(self):
        super().__init__(WorkerType.DEBRIEF)

    def execute(self, payload: dict) -> str:
        """
        Execute a debrief command.

        payload includes:
          - command: "/digest" or "/debrief"
          - args: optional timeframe (today, week, month)
        """
        command = payload.get("command", "").lower()
        args = payload.get("args", "")

        try:
            from agents.orchestrator import command_handler
        except ImportError as e:
            return f"❌ Failed to import command handlers: {e}"

        handlers = {
            "/digest": command_handler.cmd_digest,
            "/debrief": command_handler.cmd_debrief,
        }

        handler = handlers.get(command)
        if not handler:
            return f"❌ Unknown debrief command: {command}"

        try:
            result = handler(args)
            return result
        except Exception as e:
            return f"❌ Debrief error: {str(e)}"


def run(routed_task) -> str:
    """Entrypoint for the debrief worker."""
    worker = DebriefWorker()
    return worker.run(routed_task)

"""
Inbox Triage Worker

Handles quick capture commands: /note, /task, /place, /places, /bucketlist
Restricted to SQLite tools (places_db, notes_db, task_db).

This is a thin wrapper around the existing command handlers in command_handler.py,
scoped to inbox-triage operations only.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.orchestrator.worker_base import BaseWorker
from agents.orchestrator.worker_registry import WorkerType


class InboxTriageWorker(BaseWorker):
    """Handles note, task, place capture."""

    def __init__(self):
        super().__init__(WorkerType.INBOX_TRIAGE)

    def execute(self, payload: dict) -> str:
        """
        Execute an inbox triage command.

        payload should include:
          - command: e.g., "/note", "/task", "/place"
          - args: the command arguments
          - user_tier: user's tier for model selection
        """
        command = payload.get("command", "").lower()
        args = payload.get("args", "")

        # Import the handlers from the main command_handler
        try:
            from agents.orchestrator import command_handler
        except ImportError as e:
            return f"❌ Failed to import command handlers: {e}"

        # Dispatch to the appropriate handler
        handlers = {
            "/note": command_handler.cmd_note,
            "/task": command_handler.cmd_task,
            "/place": command_handler.cmd_place,
            "/places": command_handler.cmd_places,
            "/bucketlist": command_handler.cmd_bucketlist,
        }

        handler = handlers.get(command)
        if not handler:
            return f"❌ Unknown inbox triage command: {command}"

        try:
            result = handler(args)
            return result
        except Exception as e:
            return f"❌ Inbox triage error: {str(e)}"


def run(routed_task) -> str:
    """
    Entrypoint for the inbox triage worker.

    Args:
        routed_task: RoutedTask from router.route_command()

    Returns:
        Result string.
    """
    worker = InboxTriageWorker()
    return worker.run(routed_task)

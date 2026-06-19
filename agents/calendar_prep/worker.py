"""
Calendar Prep Worker (MVP stub)

Handles /appointment and /schedule commands.
Restricted to calendar_db, notes_db, and llm tools.

Currently delegates to existing command handlers.
Will integrate with Google Calendar API in future iterations.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.orchestrator.worker_base import BaseWorker
from agents.orchestrator.worker_registry import WorkerType


class CalendarPrepWorker(BaseWorker):
    """Handles calendar and appointment operations."""

    def __init__(self):
        super().__init__(WorkerType.CALENDAR_PREP)

    def execute(self, payload: dict) -> str:
        """
        Execute a calendar command.

        payload includes:
          - command: "/appointment" or "/schedule"
          - args: command arguments
          - user_tier: for model selection
        """
        command = payload.get("command", "").lower()
        args = payload.get("args", "")

        try:
            from agents.orchestrator import command_handler
        except ImportError as e:
            return f"❌ Failed to import command handlers: {e}"

        handlers = {
            "/appointment": command_handler.cmd_appointment,
            "/schedule": command_handler.cmd_schedule,
        }

        handler = handlers.get(command)
        if not handler:
            return f"❌ Unknown calendar command: {command}"

        try:
            result = handler(args)
            return result
        except Exception as e:
            return f"❌ Calendar prep error: {str(e)}"


def run(routed_task) -> str:
    """Entrypoint for the calendar prep worker."""
    worker = CalendarPrepWorker()
    return worker.run(routed_task)

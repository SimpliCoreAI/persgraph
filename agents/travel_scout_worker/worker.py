"""
Travel Scout Worker (MVP stub)

Handles /TripToggle, /explore_* commands.
Restricted to places_db, explore_state, maps, llm.
Uses supabase, google_maps, and chroma services.

Currently delegates to existing explore mode handlers.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.orchestrator.worker_base import BaseWorker
from agents.orchestrator.worker_registry import WorkerType


class TravelScoutWorker(BaseWorker):
    """Handles travel exploration and recommendations."""

    def __init__(self):
        super().__init__(WorkerType.TRAVEL_SCOUT)

    def execute(self, payload: dict) -> str:
        """
        Execute a travel scout command.

        payload includes:
          - command: "/triptoggle", "/explore_*"
          - args: command arguments
        """
        command = payload.get("command", "").lower()
        args = payload.get("args", "")

        try:
            from agents.orchestrator import command_handler
        except ImportError as e:
            return f"❌ Failed to import command handlers: {e}"

        handlers = {
            "/triptoggle": command_handler.cmd_triptoggle,
            "/explore_accept": command_handler.cmd_explore_accept,
            "/explore_click": command_handler.cmd_explore_click,
            "/explore_skip": command_handler.cmd_explore_skip,
            "/explore_bookmark": command_handler.cmd_explore_bookmark,
        }

        handler = handlers.get(command)
        if not handler:
            return f"❌ Unknown travel scout command: {command}"

        try:
            result = handler(args)
            return result
        except Exception as e:
            return f"❌ Travel scout error: {str(e)}"


def run(routed_task) -> str:
    """Entrypoint for the travel scout worker."""
    worker = TravelScoutWorker()
    return worker.run(routed_task)

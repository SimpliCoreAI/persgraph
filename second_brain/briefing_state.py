"""
Briefing state schema and manager for the weekly briefing agent.
State is persisted to data/briefing_state.json relative to the Persgraph root.
"""

import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class BriefingStep:
    IDLE = "IDLE"
    COLLECTING = "COLLECTING"
    COMPOSING = "COMPOSING"
    DELIVERING = "DELIVERING"
    DONE = "DONE"
    FAILED = "FAILED"


DEFAULT_STATE = {
    "current_step": BriefingStep.IDLE,
    "run_id": None,           # date string YYYY-MM-DD
    "collected": {
        "appointments": None,
        "tasks": None,
        "system_health": None,
    },
    "composed_briefing": None,
    "last_run_date": None,
    "last_run_status": None,
    "error": None,
}


class BriefingStateManager:
    def __init__(self, path: str = "data/briefing_state.json"):
        # Resolve relative to Persgraph root
        if os.path.isabs(path):
            self.path = path
        else:
            self.path = os.path.join(BASE_DIR, path)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def load(self) -> dict:
        """Load state from disk, returning default state if file doesn't exist."""
        if not os.path.exists(self.path):
            return dict(DEFAULT_STATE)
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
            # Merge with defaults to handle schema evolution
            state = dict(DEFAULT_STATE)
            state.update(data)
            # Ensure collected sub-keys exist
            for key in DEFAULT_STATE["collected"]:
                state["collected"].setdefault(key, None)
            return state
        except (json.JSONDecodeError, KeyError):
            return dict(DEFAULT_STATE)

    def save(self, state: dict):
        """Persist state to disk (atomic write)."""
        tmp_path = self.path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(state, f, indent=2, default=str)
        os.replace(tmp_path, self.path)

    def transition(self, step: str, **updates):
        """
        Load current state, set current_step=step, apply any extra updates, then save.
        Returns the updated state dict.
        """
        state = self.load()
        state["current_step"] = step
        for key, value in updates.items():
            if key == "collected" and isinstance(value, dict):
                state["collected"].update(value)
            else:
                state[key] = value
        self.save(state)
        return state

    def reset(self):
        """Reset state to IDLE (clears all run data)."""
        import copy
        state = copy.deepcopy(DEFAULT_STATE)
        self.save(state)
        return state

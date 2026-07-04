#!/usr/bin/env python3
"""
Compatibility wrapper for the learning worker.

The actual implementation has moved to agents/learning-worker/learning_worker.py
This wrapper is kept for backward compatibility and re-exports all public
symbols so tests can patch them at module level (e.g. scripts.learning_worker.learning_db).
"""
import sys
import os
import importlib.util

# Add parent directory to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

# Load the module from the new location using importlib (handles hyphens in dir names)
LEARNING_WORKER_PATH = os.path.join(PROJECT_ROOT, "agents", "learning-worker", "learning_worker.py")
spec = importlib.util.spec_from_file_location("learning_worker_module", LEARNING_WORKER_PATH)
learning_worker_module = importlib.util.module_from_spec(spec)
sys.modules["learning_worker_module"] = learning_worker_module
spec.loader.exec_module(learning_worker_module)

# Re-export all public symbols at module level so tests can patch via
# `scripts.learning_worker.<name>` (e.g. monkeypatch.setattr(lw, "learning_db", ...))
from second_brain import learning_db  # noqa: E402 -- must come after sys.path setup

# Constants -- accessed via getattr to preserve any internal string value exactly
_lw = learning_worker_module
EPOCH              = getattr(_lw, "EPOCH")
EVENT_CURSOR_KEY   = getattr(_lw, "EVENT_CURSOR_KEY")
OUTCOME_CURSOR_KEY = getattr(_lw, "OUTCOME_CURSOR_KEY")
LAST_RUN_KEY       = getattr(_lw, "LAST_RUN_KEY")
MIN_SIGNALS        = getattr(_lw, "MIN_SIGNALS")

# Public functions -- re-exported for direct use and test patching
run_learner                  = _lw.run_learner
extract_category_preferences = _lw.extract_category_preferences
extract_cadence_drift        = _lw.extract_cadence_drift
extract_command_patterns     = _lw.extract_command_patterns
extract_judged_quality       = _lw.extract_judged_quality
_get_cursor                  = _lw._get_cursor
_set_cursor                  = _lw._set_cursor


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PersGraph Learning Worker")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no writes")
    parser.add_argument("--force", action="store_true", help="Reprocess all records from beginning")
    args = parser.parse_args()
    run_learner(dry_run=args.dry_run, force=args.force)

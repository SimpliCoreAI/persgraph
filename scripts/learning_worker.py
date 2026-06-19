#!/usr/bin/env python3
"""
Compatibility wrapper for the learning worker.

The actual implementation has moved to agents/learning-worker/learning_worker.py
This wrapper is kept for backward compatibility.
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

run_learner = learning_worker_module.run_learner

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="PersGraph Learning Worker")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no writes")
    parser.add_argument("--force", action="store_true", help="Reprocess all records from beginning")
    args = parser.parse_args()
    run_learner(dry_run=args.dry_run, force=args.force)

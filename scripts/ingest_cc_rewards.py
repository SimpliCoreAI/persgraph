#!/usr/bin/env python3
"""
Compatibility wrapper for CC rewards ingest.

The actual implementation has moved to agents/ingest-worker/ingest_cc_rewards.py
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
INGEST_CC_PATH = os.path.join(PROJECT_ROOT, "agents", "ingest-worker", "ingest_cc_rewards.py")
spec = importlib.util.spec_from_file_location("ingest_cc_module", INGEST_CC_PATH)
ingest_cc_module = importlib.util.module_from_spec(spec)
sys.modules["ingest_cc_module"] = ingest_cc_module
spec.loader.exec_module(ingest_cc_module)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    ingest_cc_module.ingest_all(dry_run=args.dry_run)

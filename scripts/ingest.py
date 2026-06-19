#!/usr/bin/env python3
"""
Compatibility wrapper for the ingest CLI.

The actual implementation has moved to agents/ingest-worker/ingest.py
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
INGEST_PATH = os.path.join(PROJECT_ROOT, "agents", "ingest-worker", "ingest.py")
spec = importlib.util.spec_from_file_location("ingest_module", INGEST_PATH)
ingest_module = importlib.util.module_from_spec(spec)
sys.modules["ingest_module"] = ingest_module
spec.loader.exec_module(ingest_module)

# Re-export app for CLI
app = ingest_module.app

if __name__ == "__main__":
    app()

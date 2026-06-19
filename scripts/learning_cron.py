#!/usr/bin/env python3
"""
Compatibility wrapper for the learning cron trigger.

The actual implementation has moved to agents/learning-worker/cron_trigger.py
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
CRON_TRIGGER_PATH = os.path.join(PROJECT_ROOT, "agents", "learning-worker", "cron_trigger.py")
spec = importlib.util.spec_from_file_location("cron_trigger_module", CRON_TRIGGER_PATH)
cron_trigger_module = importlib.util.module_from_spec(spec)
sys.modules["cron_trigger_module"] = cron_trigger_module
spec.loader.exec_module(cron_trigger_module)

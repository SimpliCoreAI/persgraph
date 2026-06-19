#!/usr/bin/env python3
"""Compatibility wrapper for explore mode helpers."""
import importlib.util
import sys
from pathlib import Path

# Load agents/travel-scout/explore_mode_helpers.py dynamically to handle hyphenated directory
module_path = Path(__file__).parent.parent / "agents" / "travel-scout" / "explore_mode_helpers.py"
spec = importlib.util.spec_from_file_location("travel_scout.explore_mode_helpers", module_path)
explore_mode_helpers_module = importlib.util.module_from_spec(spec)
sys.modules["travel_scout.explore_mode_helpers"] = explore_mode_helpers_module
spec.loader.exec_module(explore_mode_helpers_module)

# Re-export all symbols from the actual module
from travel_scout.explore_mode_helpers import *  # noqa: F401,F403

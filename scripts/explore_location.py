#!/usr/bin/env python3
"""Compatibility wrapper for explore location helper."""
import importlib.util
import sys
from pathlib import Path

# Load agents/travel-scout/explore_location.py dynamically to handle hyphenated directory
module_path = Path(__file__).parent.parent / "agents" / "travel-scout" / "explore_location.py"
spec = importlib.util.spec_from_file_location("travel_scout.explore_location", module_path)
explore_location_module = importlib.util.module_from_spec(spec)
sys.modules["travel_scout.explore_location"] = explore_location_module
spec.loader.exec_module(explore_location_module)

# Re-export all symbols from the actual module
from travel_scout.explore_location import *  # noqa: F401,F403

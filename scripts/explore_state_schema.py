#!/usr/bin/env python3
"""Compatibility wrapper for explore state schema."""
import importlib.util
import sys
from pathlib import Path

# Load agents/travel-scout/explore_state_schema.py dynamically to handle hyphenated directory
module_path = Path(__file__).parent.parent / "agents" / "travel-scout" / "explore_state_schema.py"
spec = importlib.util.spec_from_file_location("travel_scout.explore_state_schema", module_path)
explore_state_schema_module = importlib.util.module_from_spec(spec)
sys.modules["travel_scout.explore_state_schema"] = explore_state_schema_module
spec.loader.exec_module(explore_state_schema_module)

# Re-export all symbols from the actual module
from travel_scout.explore_state_schema import *  # noqa: F401,F403

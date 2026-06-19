#!/usr/bin/env python3
"""Compatibility wrapper for explore mode worker."""
import importlib.util
import sys
from pathlib import Path

# Load agents/travel-scout/explore_mode.py dynamically to handle hyphenated directory
module_path = Path(__file__).parent.parent / "agents" / "travel-scout" / "explore_mode.py"
spec = importlib.util.spec_from_file_location("travel_scout.explore_mode", module_path)
explore_mode_module = importlib.util.module_from_spec(spec)
sys.modules["travel_scout.explore_mode"] = explore_mode_module
spec.loader.exec_module(explore_mode_module)

# Re-export all symbols from the actual module
from travel_scout.explore_mode import *  # noqa: F401,F403

if __name__ == "__main__":
    from travel_scout.explore_mode import main
    raise SystemExit(main())

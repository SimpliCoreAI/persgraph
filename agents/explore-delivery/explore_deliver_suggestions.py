#!/usr/bin/env python3
"""
Explore Mode Suggestion Delivery for OpenClaw Cron

This script is designed to run from OpenClaw cron (not system cron).
It performs an explore mode check and delivers real suggestions to Telegram
via OpenClaw's native message path.

When run from OpenClaw cron:
- Real suggestions print to stdout → delivered to Telegram
- Skipped checks (expired/disabled/cadence) print nothing → no spam
- Errors exit with status 1 → logged by cron system

Usage:
    # Configure via OpenClaw gateway:
    cron add schedule="0 * * * *" name="Explore Mode Delivery" \\
        command="cd /root/AgenticHub/Persgraph && PYTHONPATH=. .venv/bin/python agents/explore-delivery/explore_deliver_suggestions.py"

Safe to run multiple times (skips expired/disabled checks just like explore_mode.py).
"""

from __future__ import annotations

import sys
import logging
import importlib.util
from pathlib import Path

# Setup logging to stderr (cron captures stdout for Telegram, stderr for logs)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

# Add parent to path for imports
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

def deliver_suggestion() -> int:
    """
    Run one explore mode check and deliver to Telegram if suggestion is real.
    
    Returns:
        0 if check ran successfully (whether suggestion was delivered or skipped)
        1 if an error occurred
    
    Behavior:
        - Real suggestions: prints human-readable message to stdout → Telegram delivery
        - Skipped checks: prints nothing to stdout → no Telegram message
        - Errors: logs to stderr and exits 1
    """
    try:
        # Load explore_mode dynamically (handles hyphenated directory)
        module_path = ROOT / "agents" / "travel-scout" / "explore_mode.py"
        spec = importlib.util.spec_from_file_location("travel_scout.explore_mode", module_path)
        explore_mode_module = importlib.util.module_from_spec(spec)
        sys.modules["travel_scout.explore_mode"] = explore_mode_module
        spec.loader.exec_module(explore_mode_module)
        
        # Now import the function we need
        from travel_scout.explore_mode import check_once
        
        # Run the check - this returns (ok, message) where:
        #   ok=True means a suggestion was generated
        #   ok=False means the check was skipped (not an error)
        ok, message = check_once()
        
        if ok:
            # A real suggestion was generated - print it for Telegram delivery
            print(message)
            logger.info("Suggestion delivered")
        else:
            # Check was skipped (disabled, expired, cadence not met, etc.)
            # This is normal behavior - don't spam Telegram
            logger.debug(f"Check skipped: {message}")
        
        return 0
        
    except Exception as e:
        logger.exception(f"Explore delivery error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(deliver_suggestion())

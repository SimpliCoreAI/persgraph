#!/usr/bin/env python3
"""Compatibility module for the command entrypoint."""
from agents.orchestrator.command_handler import *  # noqa: F401,F403

if __name__ == "__main__":
    from agents.orchestrator.command_handler import main
    raise SystemExit(main())

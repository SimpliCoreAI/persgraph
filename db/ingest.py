#!/usr/bin/env python3
"""
Compatibility wrapper for database ingest helpers.

The actual implementation has moved to agents/ingest-worker/db_helpers.py
This wrapper is kept for backward compatibility.
"""
import sys
import os
import importlib.util

# Add parent directory to path  
DB_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(DB_DIR)
sys.path.insert(0, PROJECT_ROOT)

# Load the module from the new location using importlib (handles hyphens in dir names)
DB_HELPERS_PATH = os.path.join(PROJECT_ROOT, "agents", "ingest-worker", "db_helpers.py")
spec = importlib.util.spec_from_file_location("db_helpers_module", DB_HELPERS_PATH)
db_helpers_module = importlib.util.module_from_spec(spec)
sys.modules["db_helpers_module"] = db_helpers_module
spec.loader.exec_module(db_helpers_module)

# Re-export key functions
get_connection = db_helpers_module.get_connection
ingest_csv = db_helpers_module.ingest_csv
main = db_helpers_module.main

if __name__ == "__main__":
    main()

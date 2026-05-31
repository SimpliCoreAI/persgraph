"""
Notes / Tasks / Appointments — public API.

Delegates to notes_db (SQLite) — no ChromaDB / Ollama dependency.
All callers that import from second_brain.notes continue to work unchanged.
"""

from .notes_db import (  # noqa: F401  (re-export)
    TYPES,
    save,
    search,
    list_all,
    delete,
    count,
    get_by_id,
    bulk_import,
)

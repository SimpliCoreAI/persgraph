"""
PersGraph Worker Registry

Defines worker types, tool/scope boundaries, and capabilities for the MVP.
This scaffolding enables command → worker routing with strict capability isolation.

Worker Types:
  - inbox_triage: /note, /task, /place, /places → quick capture agents
  - calendar_prep: /appointment, /schedule → calendar integration
  - travel_scout: /TripToggle, explore_* commands → travel recommendations
  - ingest: /ingest, /wiki-ingest → knowledge ingestion
  - debrief: /digest, /debrief → summary generation

Tool/Scope Boundaries:
  - Each worker declares allowed tools (api_keys, databases, services)
  - Orchestrator enforces scoping via explicit pass-through or isolation
  - No cross-worker capability leakage by default
"""

from dataclasses import dataclass
from typing import Set, List
from enum import Enum


class WorkerType(Enum):
    """Supported worker types in the MVP."""
    INBOX_TRIAGE = "inbox_triage"
    CALENDAR_PREP = "calendar_prep"
    TRAVEL_SCOUT = "travel_scout"
    INGEST = "ingest"
    DEBRIEF = "debrief"


@dataclass
class WorkerCapabilities:
    """Defines what a worker can access."""
    worker_type: WorkerType
    allowed_tools: Set[str]  # e.g., {"places_db", "notes_db", "ollama"}
    allowed_services: Set[str]  # e.g., {"chroma", "supabase"}
    requires_external_api: bool  # True if needs API keys
    description: str

    def can_use(self, tool: str) -> bool:
        """Check if worker is allowed to use a tool."""
        return tool in self.allowed_tools

    def can_access(self, service: str) -> bool:
        """Check if worker is allowed to access a service."""
        return service in self.allowed_services


# MVP Worker Definitions
WORKER_CAPABILITIES: dict[WorkerType, WorkerCapabilities] = {
    WorkerType.INBOX_TRIAGE: WorkerCapabilities(
        worker_type=WorkerType.INBOX_TRIAGE,
        allowed_tools={"places_db", "notes_db", "task_db"},
        allowed_services={"sqlite"},
        requires_external_api=False,
        description="Quick capture: notes, tasks, places. No external services.",
    ),
    WorkerType.CALENDAR_PREP: WorkerCapabilities(
        worker_type=WorkerType.CALENDAR_PREP,
        allowed_tools={"calendar_db", "notes_db", "llm"},
        allowed_services={"google_calendar", "notion"},
        requires_external_api=True,
        description="Calendar management: appointments, schedules. Requires Google Calendar API.",
    ),
    WorkerType.TRAVEL_SCOUT: WorkerCapabilities(
        worker_type=WorkerType.TRAVEL_SCOUT,
        allowed_tools={"places_db", "explore_state", "maps", "llm"},
        allowed_services={"supabase", "google_maps", "chroma"},
        requires_external_api=True,
        description="Travel exploration & recommendations. Requires maps API.",
    ),
    WorkerType.INGEST: WorkerCapabilities(
        worker_type=WorkerType.INGEST,
        allowed_tools={"chroma", "ollama", "url_fetcher", "wikipedia", "docs_storage"},
        allowed_services={"chroma", "ollama", "supabase"},
        requires_external_api=False,
        description="Knowledge ingestion: URL parsing, embedding, chunking. Uses ChromaDB + Ollama.",
    ),
    WorkerType.DEBRIEF: WorkerCapabilities(
        worker_type=WorkerType.DEBRIEF,
        allowed_tools={"chroma", "llm", "calendar_db", "places_db", "notes_db"},
        allowed_services={"chroma", "supabase"},
        requires_external_api=False,
        description="Summary generation: digests, debriefs. Reads from all DBs, no writes.",
    ),
}


def get_worker_for_command(command: str) -> WorkerType | None:
    """
    Maps a command string to the appropriate worker type.

    Args:
        command: e.g., "/ask", "/note", "/ingest"

    Returns:
        WorkerType or None if command doesn't map to a worker.
    """
    # Normalize command
    cmd = command.lower().strip()
    if not cmd.startswith("/"):
        cmd = "/" + cmd

    # Command → Worker mapping
    command_to_worker = {
        # Inbox triage
        "/note": WorkerType.INBOX_TRIAGE,
        "/task": WorkerType.INBOX_TRIAGE,
        "/place": WorkerType.INBOX_TRIAGE,
        "/places": WorkerType.INBOX_TRIAGE,
        "/bucketlist": WorkerType.INBOX_TRIAGE,
        
        # Calendar prep
        "/appointment": WorkerType.CALENDAR_PREP,
        "/schedule": WorkerType.CALENDAR_PREP,
        
        # Travel scout
        "/triptoggle": WorkerType.TRAVEL_SCOUT,
        "/explore_accept": WorkerType.TRAVEL_SCOUT,
        "/explore_click": WorkerType.TRAVEL_SCOUT,
        "/explore_skip": WorkerType.TRAVEL_SCOUT,
        "/explore_bookmark": WorkerType.TRAVEL_SCOUT,
        
        # Ingest
        "/ingest": WorkerType.INGEST,
        "/wiki-ingest": WorkerType.INGEST,
        "/wiki_ingest": WorkerType.INGEST,
        
        # Debrief
        "/digest": WorkerType.DEBRIEF,
        "/debrief": WorkerType.DEBRIEF,
        
        # Multi-domain (handled by orchestrator, no single worker)
        "/ask": None,  # Uses query orchestrator, not a direct worker
        "/email": None,  # External email handler
        "/sport": None,  # External sports service
        
        # Metadata/help
        "/pghelp": None,
        "/status": None,
    }

    return command_to_worker.get(cmd)


def get_capabilities(worker_type: WorkerType) -> WorkerCapabilities | None:
    """Retrieve full capabilities for a worker type."""
    return WORKER_CAPABILITIES.get(worker_type)


def enforce_capability(worker_type: WorkerType, required_tool: str) -> bool:
    """
    Check if worker can use a required tool.
    Can be used to reject operations early if a tool is not in scope.

    Args:
        worker_type: The worker attempting to use the tool
        required_tool: The tool being requested

    Returns:
        True if allowed; False otherwise
    """
    cap = get_capabilities(worker_type)
    if not cap:
        return False
    return cap.can_use(required_tool)


def list_workers() -> List[WorkerType]:
    """Return all registered worker types."""
    return list(WORKER_CAPABILITIES.keys())


def describe_worker(worker_type: WorkerType) -> dict:
    """Return a detailed description of a worker."""
    cap = get_capabilities(worker_type)
    if not cap:
        return {}
    return {
        "type": worker_type.value,
        "description": cap.description,
        "allowed_tools": list(cap.allowed_tools),
        "allowed_services": list(cap.allowed_services),
        "requires_external_api": cap.requires_external_api,
    }

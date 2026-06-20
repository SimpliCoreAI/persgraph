"""Constants and enums for the cost agent."""

from enum import Enum
from pathlib import Path

# ─────── Paths ──────────────────────────────────────────────────────────────

COST_AGENT_DIR = Path(__file__).parent.parent
DATA_DIR = COST_AGENT_DIR.parent.parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# State file: tracks last observation processed
STATE_FILE = DATA_DIR / "cost_agent_state.json"

# Cost data files
COST_BY_USER_FILE = DATA_DIR / "cost_by_user.json"
COST_BY_OPERATION_FILE = DATA_DIR / "cost_by_operation.json"
COST_BY_MODEL_FILE = DATA_DIR / "cost_by_model.json"

# ─────── Langfuse Constants ──────────────────────────────────────────────────

# Standard trace tags for cost extraction
TRACE_TAGS = {
    "user_id": "user_id",           # User Telegram ID
    "operation": "operation",        # Operation type (ask, ingest, query, etc.)
    "llm_type": "llm_type",         # Type of LLM (anthropic, ollama, etc.)
    "model": "model",                # Specific model name
    "domain": "domain",              # Domain (email, query, place, etc.)
}

# Cost-related tags for filtering
COST_AGENT_TAG = "cost-tracked"

# Poller configuration defaults
DEFAULT_POLL_INTERVAL_SECONDS = 300  # 5 minutes
DEFAULT_BATCH_SIZE = 100             # Observations per fetch
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE_SECONDS = 1

# ─────── Attribution ────────────────────────────────────────────────────────

class OperationType(str, Enum):
    """Standard operation types for cost attribution."""
    ASK = "ask"                      # /ask command
    INGEST = "ingest"                # /ingest document
    QUERY = "query"                  # Knowledge base query
    PLACE = "place"                  # Place tagging
    EMAIL = "email"                  # Email classification
    CALENDAR = "calendar"            # Calendar event parsing
    DEBRIEF = "debrief"              # Activity debrief
    LEARNING = "learning"            # Learning agent
    OTHER = "other"                  # Unclassified


class LLMProvider(str, Enum):
    """Known LLM providers."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OLLAMA = "ollama"
    UNKNOWN = "unknown"


# ─────── JSON Structure Templates ──────────────────────────────────────────

def empty_cost_state() -> dict:
    """Template for cost_agent_state.json."""
    return {
        "last_seen_trace_id": None,
        "last_seen_timestamp": None,
        "last_poll_time": None,
        "poller_version": "0.1.0",
        "observations_processed": 0,
    }


def empty_cost_by_user() -> dict:
    """Template for cost_by_user.json."""
    return {
        "daily": {},    # { "YYYY-MM-DD": { user_id: cost_usd } }
        "total": {},    # { user_id: cost_usd }
    }


def empty_cost_by_operation() -> dict:
    """Template for cost_by_operation.json."""
    return {
        "daily": {},    # { "YYYY-MM-DD": { operation: cost_usd } }
        "total": {},    # { operation: cost_usd }
    }


def empty_cost_by_model() -> dict:
    """Template for cost_by_model.json."""
    return {
        "daily": {},    # { "YYYY-MM-DD": { model: cost_usd } }
        "total": {},    # { model: cost_usd }
    }


# ─────── Validation ────────────────────────────────────────────────────────

def validate_trace_id(trace_id: str | None) -> bool:
    """Check if trace_id is valid (non-empty string)."""
    return isinstance(trace_id, str) and len(trace_id) > 0


def validate_cost(cost: float) -> bool:
    """Check if cost is a valid amount (non-negative)."""
    return isinstance(cost, (int, float)) and cost >= 0

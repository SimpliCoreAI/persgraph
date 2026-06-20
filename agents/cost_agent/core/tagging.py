"""Trace tag helpers for cost attribution at command boundary."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def build_trace_tags(
    user_id: Optional[str] = None,
    operation: Optional[str] = None,
    model: Optional[str] = None,
    domain: Optional[str] = None,
    **extra_tags
) -> list[str]:
    """
    Build a list of trace tags for Langfuse cost tracking.
    
    Tags are in the format "key:value" for structured filtering.
    Use this at the command boundary to ensure all traces have proper attribution.
    
    Args:
        user_id: Telegram user ID (e.g., "8596241969")
        operation: Operation type (e.g., "ask", "ingest", "query")
        model: Model hint (e.g., "fast", "smart", or specific model name)
        domain: Domain context (e.g., "email", "calendar", "query")
        **extra_tags: Additional tags as key=value kwargs
    
    Returns:
        List of "key:value" tags
    
    Example:
        tags = build_trace_tags(
            user_id="8596241969",
            operation="ask",
            model="smart",
            domain="query"
        )
        # ["user_id:8596241969", "operation:ask", "model:smart", "domain:query"]
    """
    tags = []
    
    if user_id:
        tags.append(f"user_id:{user_id}")
    if operation:
        tags.append(f"operation:{operation}")
    if model:
        tags.append(f"model:{model}")
    if domain:
        tags.append(f"domain:{domain}")
    
    # Add extra tags
    for key, value in extra_tags.items():
        if value is not None:
            tags.append(f"{key}:{value}")
    
    return tags


def extract_operation_from_command(raw_input: str) -> Optional[str]:
    """
    Extract operation type from raw command input.
    
    Maps slash commands to operation types:
        /ask → ask
        /ingest → ingest
        /query → query
        /place → place
        /email → email
        /calendar → calendar
        /debrief → debrief
        /task, /note → other
        ... etc
    
    Args:
        raw_input: Raw command string (e.g., "/ask what is RAG?")
    
    Returns:
        Operation type string, or None if unknown
    """
    if not raw_input:
        return None
    
    cmd = raw_input.strip().split()[0].lower()
    
    # Map commands to operation types
    operation_map = {
        "/ask": "ask",
        "/ingest": "ingest",
        "/wiki_ingest": "ingest",
        "/query": "query",
        "/place": "place",
        "/email": "email",
        "/calendar": "calendar",
        "/debrief": "debrief",
        "/learning": "learning",
        "/task": "other",
        "/note": "other",
        "/digest": "query",
        "/status": "other",
        "/bucketlist": "place",
    }
    
    return operation_map.get(cmd, "other")


def inject_trace_tags_into_observe(
    observe_decorator,
    tags: list[str],
) -> callable:
    """
    Helper to merge cost-tracking tags into an @observe decorator.
    
    Note: Langfuse's @observe decorator doesn't support dynamic tags easily.
    This is a utility for manual trace_event calls.
    
    For decorator-based tracing, tags should be set at definition time.
    This is provided for reference; prefer static tags in command handler.
    
    Args:
        observe_decorator: The @observe decorator reference
        tags: List of tags to add
    
    Returns:
        Modified decorator reference (returns original for compatibility)
    """
    # Langfuse @observe doesn't support tag injection at runtime easily
    # Tags should be set at decoration time
    # This is a placeholder for potential future enhancements
    return observe_decorator


if __name__ == "__main__":
    # Quick test
    tags = build_trace_tags(
        user_id="8596241969",
        operation="ask",
        model="smart",
    )
    print("Tags:", tags)
    
    op = extract_operation_from_command("/ask what is RAG?")
    print("Operation:", op)
    
    op2 = extract_operation_from_command("/ingest https://example.com")
    print("Operation:", op2)

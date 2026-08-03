"""Semantic-first routing helpers for PersGraph.

This layer classifies requests by meaning, then maps them to a workflow and
routing policy.

Phase 1: classify only, fall through to command_handler for execution.
Phase 2: WorkflowDispatcher maps workflow names → WorkerType + model policy;
         run_with_semantic_routing dispatches directly when confidence ≥ 0.6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class IntentResult:
    intent: str
    workflow: str
    model_preference: str
    confidence: float
    reason: str
    command_hint: str | None = None


_INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "capture": ("note", "task", "remember", "save", "place", "bookmark"),
    "calendar": ("appointment", "calendar", "schedule", "meeting", "remind"),
    "travel": ("travel", "trip", "hotel", "flight", "restaurant", "poi"),
    "ingest": ("ingest", "import", "index", "wiki", "url", "document"),
    "debrief": ("digest", "debrief", "summary", "brief", "recap"),
    "reasoning": ("why", "analyze", "explain", "compare", "design", "brainstorm"),
    "browse": ("search", "browse", "lookup", "find", "research"),
}


def classify_request(text: str, command_hint: str | None = None) -> IntentResult:
    normalized = (text or "").strip().lower()
    tokens = set(normalized.replace("/", " ").replace("-", " ").split())

    def score(intent: str) -> int:
        return sum(1 for kw in _INTENT_KEYWORDS[intent] if kw in normalized or kw in tokens)

    scored = sorted(((score(intent), intent) for intent in _INTENT_KEYWORDS), reverse=True)
    top_score, top_intent = scored[0] if scored else (0, "reasoning")

    if command_hint:
        hint = command_hint.lower().strip()
        if hint in {"/note", "/task", "/place", "/places", "/bucketlist"}:
            top_intent = "capture"
        elif hint in {"/appointment", "/schedule"}:
            top_intent = "calendar"
        elif hint in {"/ingest", "/wiki-ingest", "/wiki_ingest"}:
            top_intent = "ingest"
        elif hint in {"/digest", "/debrief"}:
            top_intent = "debrief"
        elif hint in {"/ask"}:
            top_intent = "reasoning"

    workflow_map = {
        "capture": "capture_workflow",
        "calendar": "calendar_workflow",
        "travel": "travel_workflow",
        "ingest": "ingest_workflow",
        "debrief": "debrief_workflow",
        "reasoning": "reasoning_workflow",
        "browse": "browse_workflow",
    }
    model_map = {
        "capture": "haiku",
        "calendar": "gemini",
        "travel": "openai",
        "ingest": "haiku",
        "debrief": "sonnet",
        "reasoning": "sonnet",
        "browse": "smart",
    }

    confidence = 0.9 if top_score >= 2 else 0.55 if top_score == 1 else 0.35
    reason = f"matched intent '{top_intent}' with score {top_score}"
    return IntentResult(
        intent=top_intent,
        workflow=workflow_map[top_intent],
        model_preference=model_map[top_intent],
        confidence=confidence,
        reason=reason,
        command_hint=command_hint,
    )


def route_semantically(text: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = context or {}
    command_hint = context.get("command")
    intent = classify_request(text, command_hint=command_hint)
    return {
        "intent": intent.intent,
        "workflow": intent.workflow,
        "model_preference": intent.model_preference,
        "confidence": intent.confidence,
        "reason": intent.reason,
        "command_hint": intent.command_hint,
        "route_kind": "semantic-first",
    }


# ---------------------------------------------------------------------------
# Phase 2 — WorkflowDispatcher
# ---------------------------------------------------------------------------

# Minimum confidence to dispatch via semantic route instead of falling back
SEMANTIC_DISPATCH_THRESHOLD: float = 0.6

# Model preference → LiteLLM virtual tier mapping
_MODEL_POLICY: dict[str, str] = {
    "haiku": "fast",
    "sonnet": "smart",
    "gemini": "smart",
    "openai": "smart",
    "perplexity": "smart",
}


@dataclass(frozen=True)
class DispatchDecision:
    """Outcome of WorkflowDispatcher.resolve()."""

    workflow: str
    worker_type_value: str | None   # WorkerType.value string, or None for orchestrator-handled
    model_tier: str                  # LiteLLM virtual tier: 'fast' | 'smart'
    fallback_command: str | None    # e.g. '/note' — used when confidence is below threshold
    confidence: float
    dispatched_semantically: bool   # True when above threshold
    reason: str


# Workflow → canonical fallback command used when reverting to command_handler
_WORKFLOW_FALLBACK_COMMAND: dict[str, str | None] = {
    "capture_workflow": "/note",
    "calendar_workflow": "/appointment",
    "travel_workflow": "/triptoggle",
    "ingest_workflow": "/ingest",
    "debrief_workflow": "/digest",
    "reasoning_workflow": "/ask",
    "browse_workflow": "/ask",
}

# Workflow → WorkerType value string (matches WorkerType enum values)
_WORKFLOW_TO_WORKER: dict[str, str | None] = {
    "capture_workflow": "inbox_triage",
    "calendar_workflow": "calendar_prep",
    "travel_workflow": "travel_scout",
    "ingest_workflow": "ingest",
    "debrief_workflow": "debrief",
    "reasoning_workflow": None,   # handled by orchestrator directly
    "browse_workflow": None,      # handled by orchestrator directly
}


class WorkflowDispatcher:
    """Maps IntentResult → DispatchDecision, including model policy and fallback.

    Phase 2 contract:
    - If confidence >= SEMANTIC_DISPATCH_THRESHOLD: dispatch semantically.
    - If confidence < threshold: return fallback_command so the caller can
      rewrite the input and fall through to route_command_with_gates().
    """

    def __init__(self, threshold: float = SEMANTIC_DISPATCH_THRESHOLD):
        self.threshold = threshold

    def resolve(self, intent: IntentResult) -> DispatchDecision:
        """Turn an IntentResult into a concrete DispatchDecision."""
        above_threshold = intent.confidence >= self.threshold
        model_tier = _MODEL_POLICY.get(intent.model_preference, "fast")
        worker_value = _WORKFLOW_TO_WORKER.get(intent.workflow)
        fallback_cmd = _WORKFLOW_FALLBACK_COMMAND.get(intent.workflow)

        reason = (
            f"semantic dispatch (confidence={intent.confidence:.2f} >= {self.threshold})"
            if above_threshold
            else f"fallback to command_handler (confidence={intent.confidence:.2f} < {self.threshold})"
        )

        return DispatchDecision(
            workflow=intent.workflow,
            worker_type_value=worker_value,
            model_tier=model_tier,
            fallback_command=fallback_cmd,
            confidence=intent.confidence,
            dispatched_semantically=above_threshold,
            reason=reason,
        )


# Module-level singleton for convenience
_default_dispatcher = WorkflowDispatcher()


def dispatch_intent(
    text: str,
    context: dict[str, Any] | None = None,
    threshold: float = SEMANTIC_DISPATCH_THRESHOLD,
) -> DispatchDecision:
    """Classify *text* and resolve a DispatchDecision in one call.

    Args:
        text: Raw user text.
        context: Optional dict; may include ``command`` (slash hint).
        threshold: Override the default confidence threshold.

    Returns:
        DispatchDecision with workflow, worker, model_tier, and fallback info.
    """
    ctx = context or {}
    command_hint = ctx.get("command")
    intent = classify_request(text, command_hint=command_hint)
    dispatcher = WorkflowDispatcher(threshold=threshold)
    return dispatcher.resolve(intent)

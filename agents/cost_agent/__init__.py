"""
Cost Agent — Lightweight cost attribution and reporting aligned with Langfuse tracing.

This package provides:
  - Langfuse observation polling (async, idempotent)
  - Cost calculation (tokens × pricing tables)
  - Cost attribution (user_id, operation, model)
  - Reporting and alerting (Phase 2+)

Usage (Phase 1):
    from agents.cost_agent import run_poller
    
    # Fetch observations since last poll; calculate costs; persist to JSON
    await run_poller()

Design:
  - Passive observer: polls Langfuse asynchronously (not inline with commands)
  - Langfuse is single source of truth for cost calculation
  - JSON-based state & reporting (Phase 1); SQL migration in Phase 3
  - Backward compatible: legacy track_api_cost.py unaffected
  - Error resilient: Langfuse unavailable → skip silently

See: IMPLEMENTATION_PLAN.md for detailed scope and acceptance criteria.
"""

__version__ = "0.2.0"  # Added: Langfuse API integration, trace tags, validation
__all__ = [
    "run_poller",
    "calculate_cost",
    "extract_user_id",
    "extract_operation",
    "build_trace_tags",
    "extract_operation_from_command",
    "run_validator_smoke_test",
]

# Lazy imports to avoid circular dependencies
_poller = None
_calculator = None
_attribution = None


async def run_poller():
    """Run the Langfuse observation poller once. Safe to call multiple times."""
    global _poller
    if _poller is None:
        from agents.cost_agent.core.poller import PollerClient
        _poller = PollerClient()
    await _poller.poll_and_update()


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> tuple[float, str]:
    """Calculate cost for a model and token counts. Returns (cost_usd, provider)."""
    global _calculator
    if _calculator is None:
        from agents.cost_agent.core.calculator import CostCalculator
        _calculator = CostCalculator()
    return _calculator.calculate(model, input_tokens, output_tokens)


def extract_user_id(observation: dict) -> str | None:
    """Extract user_id from a Langfuse observation (from tags or context)."""
    global _attribution
    if _attribution is None:
        from agents.cost_agent.core.attribution import AttributionExtractor
        _attribution = AttributionExtractor()
    return _attribution.extract_user_id(observation)


def extract_operation(observation: dict) -> str | None:
    """Extract operation type from a Langfuse observation."""
    global _attribution
    if _attribution is None:
        from agents.cost_agent.core.attribution import AttributionExtractor
        _attribution = AttributionExtractor()
    return _attribution.extract_operation(observation)


def build_trace_tags(
    user_id: str | None = None,
    operation: str | None = None,
    model: str | None = None,
    domain: str | None = None,
    **extra_tags,
) -> list[str]:
    """Build trace tags for cost attribution at command boundary."""
    from agents.cost_agent.core.tagging import build_trace_tags as _build_tags
    return _build_tags(user_id=user_id, operation=operation, model=model, domain=domain, **extra_tags)


def extract_operation_from_command(raw_input: str) -> str | None:
    """Extract operation type from a slash command (e.g., /ask → ask)."""
    from agents.cost_agent.core.tagging import extract_operation_from_command as _extract_op
    return _extract_op(raw_input)


async def run_validator_smoke_test() -> dict:
    """Run comprehensive smoke test for cost agent integration. Returns test results."""
    from agents.cost_agent.core.validator import run_validator_smoke_test as _validate
    return await _validate()

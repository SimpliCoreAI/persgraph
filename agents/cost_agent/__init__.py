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

__version__ = "0.3.0"  # Added: Phase 3 reporting, summaries, event ID tracking, alerting
__all__ = [
    # Phase 1: Core
    "run_poller",
    "calculate_cost",
    "extract_user_id",
    "extract_operation",
    # Phase 2: Tagging
    "build_trace_tags",
    "extract_operation_from_command",
    "run_validator_smoke_test",
    # Phase 3: Reporting & Alerts
    "get_cost_summary",
    "export_summary",
    "check_budget_increase_alert",
    "CostSummaryBuilder",
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


# Phase 3: Reporting & Summaries

def get_cost_summary(
    group_by: str = "command",
    start_date: str | None = None,
    end_date: str | None = None,
    include_event_ids: bool = True,
    data_dir: str | None = None,
) -> dict:
    """
    Get flexible cost summaries with event ID association.
    
    Groups by: command, worker, layer, trigger, model, or date.
    Includes event_ids for feedback loop integration.
    
    Args:
        group_by: Grouping dimension
        start_date: Start date (YYYY-MM-DD) or None
        end_date: End date (YYYY-MM-DD) or None
        include_event_ids: Include event IDs (default True)
        data_dir: Path to cost data directory
    
    Returns:
        Dict with groups and event_ids
    """
    from agents.cost_agent.reporters import get_cost_summary as _get_summary
    return _get_summary(
        group_by=group_by,
        start_date=start_date,
        end_date=end_date,
        include_event_ids=include_event_ids,
        data_dir=data_dir,
    )


def export_summary(
    summary: dict,
    format: str = "text",
    output_path: str | None = None,
) -> str:
    """
    Export cost summary in multiple formats (markdown, json, csv, text).
    
    Args:
        summary: Cost summary dict from get_cost_summary()
        format: Output format (markdown, json, csv, text)
        output_path: Optional file path to write output
    
    Returns:
        Formatted string
    """
    from agents.cost_agent.reporters import export_summary as _export
    return _export(summary=summary, format=format, output_path=output_path)


def check_budget_increase_alert(
    alert_type: str = "summary",
    lookback_days: int = 7,
    data_dir: str | None = None,
) -> dict:
    """
    Check for budget increases using anomaly detection (not thresholds).
    
    Anomaly-based alerting without configuration:
    - Detects cost spikes > 2σ above baseline (standard deviation method)
    - Identifies new operations
    - Provides spending summary
    
    Args:
        alert_type: "anomaly" (spike detection), "new_ops" (new commands), "summary" (info)
        lookback_days: Days of history for baseline (default 7)
        data_dir: Path to cost data directory
    
    Returns:
        Alert dict with detected issues
    """
    from agents.cost_agent.reporters import check_budget_increase_alert as _check_alert
    return _check_alert(alert_type=alert_type, lookback_days=lookback_days, data_dir=data_dir)


class CostSummaryBuilder:
    """
    Flexible summary builder for advanced use cases.
    
    Supports multiple grouping dimensions and date range filtering.
    Each summary includes event_ids for feedback loop integration.
    """
    
    def __init__(self, data_dir: str | None = None):
        """Initialize builder."""
        from agents.cost_agent.reporters.summaries import CostSummaryBuilder as _Builder
        self._builder = _Builder(data_dir)
    
    def filter_by_date_range(self, start_date: str | None = None, end_date: str | None = None):
        """Filter records by date range."""
        return self._builder.filter_by_date_range(start_date, end_date)
    
    def summarize_by(self, group_by: str, records=None):
        """Summarize records by dimension."""
        return self._builder.summarize_by(group_by, records)
    
    def summary_hierarchy(self, start_date: str | None = None, end_date: str | None = None):
        """Generate hierarchical summary (date → command → worker → model)."""
        return self._builder.summary_hierarchy(start_date, end_date)

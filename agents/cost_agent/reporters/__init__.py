"""
Cost Agent Reporters — Phase 3 reporting and summaries with event tracking.

This module provides:
  - Flexible cost summaries (by command, worker, layer, trigger, model, date range)
  - Event ID association for feedback and continuous learning
  - Optional alerting for budget increases
  - Minimal UI (text output, JSON export)

Usage:
    from agents.cost_agent.reporters import get_cost_summary, export_summary

    # Get summary by command for date range
    summary = get_cost_summary(
        group_by="command",
        start_date="2026-06-01",
        end_date="2026-06-30",
        include_event_ids=True,
    )
    
    # Export as JSON/CSV/Markdown
    export_summary(summary, format="markdown", output_path="report.md")
"""

__all__ = [
    "get_cost_summary",
    "export_summary",
    "check_budget_increase_alert",
    "CostSummaryBuilder",
]

from agents.cost_agent.reporters.summaries import (
    get_cost_summary,
    CostSummaryBuilder,
)
from agents.cost_agent.reporters.export import export_summary
from agents.cost_agent.reporters.alerts import check_budget_increase_alert

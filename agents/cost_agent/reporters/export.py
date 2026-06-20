"""
Cost summary export formats: Markdown, JSON, CSV, plaintext.

Supports minimal UI output (text-based reporting).
"""

import json
import csv
from pathlib import Path
from typing import Literal, Optional
from datetime import datetime


def export_summary(
    summary: dict,
    format: Literal["markdown", "json", "csv", "text"] = "text",
    output_path: Optional[str] = None,
) -> str:
    """
    Export cost summary in multiple formats.
    
    Args:
        summary: Cost summary dict from get_cost_summary()
        format: Output format (markdown, json, csv, text)
        output_path: Optional file path to write output
    
    Returns:
        Formatted string
    """
    if format == "markdown":
        output = _format_markdown(summary)
    elif format == "json":
        output = _format_json(summary)
    elif format == "csv":
        output = _format_csv(summary)
    else:  # text
        output = _format_text(summary)
    
    if output_path:
        Path(output_path).write_text(output)
    
    return output


def _format_text(summary: dict) -> str:
    """Plain text format (simple, readable)."""
    lines = [
        "COST SUMMARY",
        "=" * 60,
        "",
    ]
    
    total_cost = sum(g["total_cost"] for g in summary.values() if isinstance(g, dict))
    total_events = sum(g["count"] for g in summary.values() if isinstance(g, dict))
    
    lines.extend([
        f"Total Cost: ${total_cost:.2f}",
        f"Total Events: {total_events}",
        f"Generated: {datetime.now().isoformat()}",
        "",
        "BY GROUP",
        "-" * 60,
    ])
    
    for key, group in sorted(summary.items()):
        if not isinstance(group, dict):
            continue
        lines.extend([
            f"\n{key}:",
            f"  Cost: ${group['total_cost']:.2f}",
            f"  Count: {group['count']}",
            f"  Avg: ${group['avg_cost']:.4f}/op",
            f"  Events: {len(group.get('event_ids', []))}",
        ])
    
    return "\n".join(lines)


def _format_markdown(summary: dict) -> str:
    """Markdown format (for reports, emails)."""
    lines = [
        "# Cost Summary Report",
        "",
        f"**Generated:** {datetime.now().isoformat()}",
        "",
    ]
    
    total_cost = sum(g["total_cost"] for g in summary.values() if isinstance(g, dict))
    total_events = sum(g["count"] for g in summary.values() if isinstance(g, dict))
    
    lines.extend([
        "## Overview",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Cost | ${total_cost:.2f} |",
        f"| Total Operations | {total_events} |",
        "",
        "## Details by Group",
        "",
        "| Group | Cost | Operations | Avg Cost/Op | Events |",
        "|-------|------|-----------|-------------|--------|",
    ])
    
    for key, group in sorted(summary.items()):
        if not isinstance(group, dict):
            continue
        lines.append(
            f"| {key} | ${group['total_cost']:.2f} | {group['count']} | "
            f"${group['avg_cost']:.4f} | {len(group.get('event_ids', []))} |"
        )
    
    lines.extend([
        "",
        "## Event Tracking",
        "",
        "Each group includes event IDs for feedback and continuous learning:",
        "",
    ])
    
    for key, group in sorted(summary.items()):
        if not isinstance(group, dict) or not group.get("event_ids"):
            continue
        lines.append(f"**{key}:** {len(group['event_ids'])} events")
        if len(group["event_ids"]) <= 10:
            for eid in group["event_ids"][:10]:
                lines.append(f"  - `{eid}`")
        else:
            lines.append(f"  - (showing first 10 of {len(group['event_ids'])})")
            for eid in group["event_ids"][:10]:
                lines.append(f"    - `{eid}`")
    
    return "\n".join(lines)


def _format_json(summary: dict) -> str:
    """JSON format (for programmatic consumption)."""
    # Add metadata
    output = {
        "metadata": {
            "generated": datetime.now().isoformat(),
            "format_version": "1.0",
        },
        "summary": summary,
        "totals": {
            "total_cost": sum(g["total_cost"] for g in summary.values() if isinstance(g, dict)),
            "total_operations": sum(g["count"] for g in summary.values() if isinstance(g, dict)),
            "total_events": sum(
                len(g.get("event_ids", [])) for g in summary.values() if isinstance(g, dict)
            ),
        },
    }
    return json.dumps(output, indent=2)


def _format_csv(summary: dict) -> str:
    """CSV format (for spreadsheets)."""
    from io import StringIO
    
    fieldnames = [
        "group",
        "cost_usd",
        "count",
        "avg_cost",
        "avg_tokens",
        "min_cost",
        "max_cost",
        "event_count",
        "first_occurrence",
        "last_occurrence",
    ]
    
    # Use StringIO to capture CSV output
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    for key, group in sorted(summary.items()):
        if not isinstance(group, dict):
            continue
        writer.writerow({
            "group": key,
            "cost_usd": f"{group['total_cost']:.4f}",
            "count": group["count"],
            "avg_cost": f"{group['avg_cost']:.4f}",
            "avg_tokens": group.get("avg_tokens", 0),
            "min_cost": f"{group.get('min_cost', 0):.4f}",
            "max_cost": f"{group.get('max_cost', 0):.4f}",
            "event_count": len(group.get("event_ids", [])),
            "first_occurrence": group.get("first_occurrence", ""),
            "last_occurrence": group.get("last_occurrence", ""),
        })
    
    return output.getvalue()

"""Formatting and serialization helpers for cost agent data."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any


class CostEncoder(json.JSONEncoder):
    """Custom JSON encoder for Decimal and date types."""
    
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


def format_json(data: dict, indent: int = 2) -> str:
    """Format data as JSON with proper encoding."""
    return json.dumps(data, cls=CostEncoder, indent=indent, sort_keys=True)


def parse_json(text: str) -> dict:
    """Parse JSON text to dict."""
    return json.loads(text)


def read_json_file(path: Path) -> dict:
    """Read JSON file; return empty dict if file doesn't exist."""
    if not path.exists():
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Failed to read {path}: {e}")
        return {}


def write_json_file(path: Path, data: dict) -> bool:
    """Write JSON file atomically (write-to-temp, then rename)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            f.write(format_json(data))
        temp_path.replace(path)
        return True
    except IOError as e:
        print(f"Error: Failed to write {path}: {e}")
        return False


def format_cost_summary(daily_costs: dict, total_cost: float) -> str:
    """Format cost data as human-readable summary (Markdown)."""
    lines = []
    lines.append("## Cost Summary\n")
    lines.append(f"**Total:** ${total_cost:.2f}\n")
    
    if daily_costs:
        lines.append("### Daily Breakdown\n")
        lines.append("| Date | Cost |\n|------|------|\n")
        for date_str in sorted(daily_costs.keys(), reverse=True):
            cost = daily_costs[date_str]
            lines.append(f"| {date_str} | ${cost:.2f} |\n")
    
    return "".join(lines)


def format_cost_by_user(data: dict) -> str:
    """Format cost data by user as table (Markdown)."""
    lines = []
    lines.append("## Cost by User\n")
    lines.append("| User ID | Cost |\n|---------|------|\n")
    
    total_cost = data.get("total", {})
    for user_id in sorted(total_cost.keys()):
        cost = total_cost[user_id]
        lines.append(f"| {user_id} | ${cost:.2f} |\n")
    
    return "".join(lines)


def format_cost_by_operation(data: dict) -> str:
    """Format cost data by operation as table (Markdown)."""
    lines = []
    lines.append("## Cost by Operation\n")
    lines.append("| Operation | Cost |\n|-----------|------|\n")
    
    total_cost = data.get("total", {})
    for op in sorted(total_cost.keys()):
        cost = total_cost[op]
        lines.append(f"| {op} | ${cost:.2f} |\n")
    
    return "".join(lines)


if __name__ == "__main__":
    # Quick test
    sample = {"daily": {"2026-06-19": 12.34}, "total": {"user_123": 45.67}}
    json_str = format_json(sample)
    print("JSON:", json_str)
    
    parsed = parse_json(json_str)
    print("Parsed:", parsed)

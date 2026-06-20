"""
Cost summaries with flexible grouping and event ID association.

Provides summaries grouped by:
  - command (operation type: ask, ingest, query, etc.)
  - worker (user_id)
  - layer (model provider: anthropic, openai, ollama, etc.)
  - trigger (source: command, scheduled, webhook, etc.)
  - model (specific model name)
  - date (daily breakdown)

Each summary includes event_ids for feedback loop integration.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Literal
from dataclasses import dataclass, asdict, field


@dataclass
class CostRecord:
    """Single cost record with event tracking."""
    event_id: str  # Unique identifier for feedback/continuous learning
    timestamp: str  # ISO 8601
    user_id: str
    operation: str
    model: str
    provider: str
    cost_usd: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    
    # Optional fields for richer context
    trigger: str = "command"  # command, scheduled, webhook, etc.
    layer: str = ""  # Provider layer (anthropic, openai, ollama)
    tags: list[str] = field(default_factory=list)


@dataclass
class SummaryGroup:
    """Summary statistics for a group of cost records."""
    key: str  # Group key (command name, user_id, model, etc.)
    count: int  # Number of operations
    total_cost: float  # Total cost in USD
    total_tokens: int  # Total tokens used
    avg_cost: float  # Average cost per operation
    avg_tokens: int  # Average tokens per operation
    event_ids: list[str] = field(default_factory=list)  # Associated event IDs
    min_cost: float = 0.0
    max_cost: float = 0.0
    first_occurrence: str = ""  # ISO 8601
    last_occurrence: str = ""  # ISO 8601
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return asdict(self)


class CostSummaryBuilder:
    """Build flexible cost summaries with multiple grouping options."""
    
    def __init__(self, data_dir: Optional[str] = None):
        """Initialize builder with optional data directory."""
        self.data_dir = Path(data_dir or "/root/AgenticHub/Persgraph/data")
        self.records: list[CostRecord] = []
        self._load_data()
    
    def _load_data(self) -> None:
        """Load cost records from JSON files."""
        self.records = []
        
        # Load from cost_agent_state.json which contains event-level data
        state_file = self.data_dir / "cost_agent_state.json"
        if state_file.exists():
            try:
                with open(state_file) as f:
                    state = json.load(f)
                    # Extract cost events from state
                    for event in state.get("cost_events", []):
                        record = self._dict_to_record(event)
                        if record:
                            self.records.append(record)
            except (json.JSONDecodeError, IOError):
                pass
        
        # Fallback: reconstruct from aggregated files if event-level data not available
        if not self.records:
            self._load_from_aggregates()
    
    def _load_from_aggregates(self) -> None:
        """Reconstruct records from aggregated JSON files (fallback)."""
        # Load cost_by_user.json
        user_file = self.data_dir / "cost_by_user.json"
        if user_file.exists():
            try:
                with open(user_file) as f:
                    data = json.load(f)
                    # Note: aggregated files lose event_id detail; use placeholder
                    for date_key, daily_costs in data.get("daily", {}).items():
                        for user_id, cost in daily_costs.items():
                            # Reconstruct event from aggregate
                            record = CostRecord(
                                event_id=f"aggregate:user:{user_id}:{date_key}",
                                timestamp=f"{date_key}T00:00:00Z",
                                user_id=user_id,
                                operation="unknown",
                                model="unknown",
                                provider="unknown",
                                cost_usd=cost,
                                input_tokens=0,
                                output_tokens=0,
                                total_tokens=0,
                            )
                            self.records.append(record)
            except (json.JSONDecodeError, IOError):
                pass
    
    def _dict_to_record(self, d: dict) -> Optional[CostRecord]:
        """Convert dict to CostRecord, handling missing fields."""
        try:
            return CostRecord(
                event_id=d.get("event_id", f"unknown:{datetime.now().isoformat()}"),
                timestamp=d.get("timestamp", datetime.now().isoformat()),
                user_id=d.get("user_id", "unknown"),
                operation=d.get("operation", "unknown"),
                model=d.get("model", "unknown"),
                provider=d.get("provider", "unknown"),
                cost_usd=float(d.get("cost_usd", 0.0)),
                input_tokens=int(d.get("input_tokens", 0)),
                output_tokens=int(d.get("output_tokens", 0)),
                total_tokens=int(d.get("total_tokens", 0)),
                trigger=d.get("trigger", "command"),
                layer=d.get("layer", ""),
                tags=d.get("tags", []),
            )
        except (ValueError, TypeError):
            return None
    
    def filter_by_date_range(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[CostRecord]:
        """Filter records by date range (ISO 8601 format: YYYY-MM-DD)."""
        filtered = []
        
        # Create timezone-aware datetimes
        start_dt = None
        end_dt = None
        if start_date:
            start_dt = datetime.fromisoformat(f"{start_date}T00:00:00+00:00")
        if end_date:
            end_dt = datetime.fromisoformat(f"{end_date}T23:59:59+00:00")
        
        for record in self.records:
            try:
                ts = record.timestamp.replace("Z", "+00:00")
                record_dt = datetime.fromisoformat(ts)
                # Ensure it's timezone-aware
                if record_dt.tzinfo is None:
                    record_dt = record_dt.replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError):
                continue
            
            if start_dt and record_dt < start_dt:
                continue
            if end_dt and record_dt > end_dt:
                continue
            
            filtered.append(record)
        
        return filtered
    
    def summarize_by(
        self,
        group_by: Literal["command", "worker", "layer", "trigger", "model", "date"],
        records: Optional[list[CostRecord]] = None,
    ) -> dict[str, SummaryGroup]:
        """
        Summarize records grouped by specified dimension.
        
        Args:
            group_by: Grouping dimension
            records: Records to summarize (defaults to all loaded records)
        
        Returns:
            Dict mapping group keys to SummaryGroup objects
        """
        records = records or self.records
        groups: dict[str, SummaryGroup] = {}
        
        for record in records:
            # Determine group key
            if group_by == "command":
                key = record.operation
            elif group_by == "worker":
                key = record.user_id
            elif group_by == "layer":
                key = record.layer or record.provider
            elif group_by == "trigger":
                key = record.trigger
            elif group_by == "model":
                key = record.model
            elif group_by == "date":
                key = record.timestamp[:10]  # YYYY-MM-DD
            else:
                key = "unknown"
            
            # Create or update group
            if key not in groups:
                groups[key] = SummaryGroup(
                    key=key,
                    count=0,
                    total_cost=0.0,
                    total_tokens=0,
                    avg_cost=0.0,
                    avg_tokens=0,
                    event_ids=[],
                    min_cost=float("inf"),
                    max_cost=0.0,
                    first_occurrence=record.timestamp,
                    last_occurrence=record.timestamp,
                )
            
            group = groups[key]
            group.count += 1
            group.total_cost += record.cost_usd
            group.total_tokens += record.total_tokens
            group.event_ids.append(record.event_id)
            group.min_cost = min(group.min_cost, record.cost_usd)
            group.max_cost = max(group.max_cost, record.cost_usd)
            group.last_occurrence = record.timestamp
        
        # Calculate averages
        for group in groups.values():
            if group.count > 0:
                group.avg_cost = group.total_cost / group.count
                group.avg_tokens = group.total_tokens // group.count
            if group.min_cost == float("inf"):
                group.min_cost = 0.0
        
        return groups
    
    def summary_hierarchy(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        """
        Generate hierarchical summary: by date → command → worker → model.
        
        Useful for understanding cost breakdown across all dimensions.
        """
        records = self.filter_by_date_range(start_date, end_date)
        
        hierarchy = {
            "period": {
                "start": start_date or "all",
                "end": end_date or "all",
            },
            "totals": {
                "records": len(records),
                "total_cost": sum(r.cost_usd for r in records),
                "total_tokens": sum(r.total_tokens for r in records),
            },
            "by_date": {},
        }
        
        by_date = self.summarize_by("date", records)
        for date_key in sorted(by_date.keys()):
            date_records = [r for r in records if r.timestamp[:10] == date_key]
            hierarchy["by_date"][date_key] = {
                "summary": by_date[date_key].to_dict(),
                "by_command": self.summarize_by("command", date_records),
                "by_worker": self.summarize_by("worker", date_records),
                "by_model": self.summarize_by("model", date_records),
            }
            # Convert nested SummaryGroup to dicts
            for dim in ["by_command", "by_worker", "by_model"]:
                hierarchy["by_date"][date_key][dim] = {
                    k: v.to_dict() for k, v in hierarchy["by_date"][date_key][dim].items()
                }
        
        return hierarchy


def get_cost_summary(
    group_by: Literal["command", "worker", "layer", "trigger", "model", "date"] = "command",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    include_event_ids: bool = True,
    data_dir: Optional[str] = None,
) -> dict:
    """
    Get a cost summary with flexible grouping and event ID association.
    
    Args:
        group_by: Grouping dimension (command, worker, layer, trigger, model, date)
        start_date: Start date (YYYY-MM-DD) or None for all
        end_date: End date (YYYY-MM-DD) or None for all
        include_event_ids: Include event IDs for feedback (default True)
        data_dir: Path to cost data directory
    
    Returns:
        Dict with summary groups, each including event_ids
        
    Example:
        >>> summary = get_cost_summary(
        ...     group_by="command",
        ...     start_date="2026-06-01",
        ...     end_date="2026-06-30",
        ... )
        >>> for cmd, group in summary.items():
        ...     print(f"{cmd}: ${group['total_cost']:.2f} ({len(group['event_ids'])} events)")
    """
    builder = CostSummaryBuilder(data_dir)
    records = builder.filter_by_date_range(start_date, end_date)
    groups = builder.summarize_by(group_by, records)
    
    # Convert to dict format
    result = {}
    for key, group in groups.items():
        result[key] = group.to_dict()
        if not include_event_ids:
            result[key].pop("event_ids", None)
    
    return result

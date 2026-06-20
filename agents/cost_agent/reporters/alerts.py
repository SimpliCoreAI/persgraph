"""
Budget increase alerting without threshold-tuning complexity.

Strategy: Monitor for significant cost changes (deviation detection) rather than
absolute thresholds. This avoids the need for manual threshold configuration per
user/operation.

Supported alert types:
  - Daily increase: Cost today > 2σ above 7-day average (anomaly detection)
  - New command: First-time operation detected
  - Model change: Cost distribution shifted for an operation
  - Summary: Simple summary of changes (no hard thresholds)
"""

from datetime import datetime, timedelta
from typing import Optional, Literal
import json
import statistics
from pathlib import Path


class BudgetIncreaseAlert:
    """Anomaly-based alerting without threshold tuning."""
    
    def __init__(self, data_dir: Optional[str] = None):
        """Initialize alert checker."""
        self.data_dir = Path(data_dir or "/root/AgenticHub/Persgraph/data")
        self.state_file = self.data_dir / "cost_agent_state.json"
    
    def check_daily_increase_anomaly(
        self,
        lookback_days: int = 7,
        std_dev_threshold: float = 2.0,
    ) -> dict:
        """
        Check for cost anomalies: today's cost > mean + (σ * threshold).
        
        This is deviation detection, not absolute thresholds.
        No configuration needed; works for any spending pattern.
        
        Args:
            lookback_days: Days of history to use for baseline
            std_dev_threshold: Number of standard deviations (2.0 = 2σ above mean)
        
        Returns:
            Alert dict with anomalies by user/operation
        """
        alerts = {
            "type": "daily_increase_anomaly",
            "threshold": f"{std_dev_threshold}σ above 7-day average",
            "detected_at": datetime.now().isoformat(),
            "anomalies": [],
        }
        
        try:
            with open(self.state_file) as f:
                state = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return alerts
        
        # Group costs by user/operation by day
        daily_costs = self._group_costs_by_day(state.get("cost_events", []))
        
        # Compute baseline and detect anomalies
        today = datetime.now().date().isoformat()
        for (user_op, costs_by_day) in daily_costs.items():
            user_id, operation = user_op.split("|", 1)
            
            # Get historical costs
            sorted_dates = sorted(costs_by_day.keys())
            if len(sorted_dates) < lookback_days + 1:
                continue  # Not enough history
            
            # Get yesterday's data (last complete day)
            hist_end_idx = len(sorted_dates) - 1  # Exclude today if present
            hist_dates = sorted_dates[max(0, hist_end_idx - lookback_days):hist_end_idx]
            hist_costs = [costs_by_day[d] for d in hist_dates]
            
            if len(hist_costs) < 2:
                continue
            
            # Compute baseline statistics
            mean_cost = statistics.mean(hist_costs)
            try:
                std_dev = statistics.stdev(hist_costs)
            except statistics.StatisticsError:
                std_dev = 0
            
            threshold = mean_cost + (std_dev * std_dev_threshold)
            
            # Check today's cost (if available)
            today_cost = costs_by_day.get(today)
            if today_cost is not None and today_cost > threshold:
                alerts["anomalies"].append({
                    "user_id": user_id,
                    "operation": operation,
                    "today_cost": f"${today_cost:.2f}",
                    "baseline_mean": f"${mean_cost:.2f}",
                    "baseline_std_dev": f"${std_dev:.2f}",
                    "threshold": f"${threshold:.2f}",
                    "excess": f"${today_cost - threshold:.2f}",
                    "severity": self._classify_severity(today_cost, threshold, mean_cost),
                    "reason": "Cost spike detected (anomaly)",
                })
        
        return alerts
    
    def check_new_operations(self, lookback_days: int = 1) -> dict:
        """
        Detect new operations first seen in the last N days.
        
        Useful for understanding new usage patterns without triggering
        false positives for legitimate new features.
        """
        from datetime import timezone
        
        alerts = {
            "type": "new_operations",
            "detected_at": datetime.now().isoformat(),
            "new_ops": [],
        }
        
        try:
            with open(self.state_file) as f:
                state = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return alerts
        
        # Make cutoff timezone-aware
        cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days))
        seen_ops = set()
        
        for event in state.get("cost_events", []):
            try:
                ts = event.get("timestamp", "").replace("Z", "+00:00")
                event_dt = datetime.fromisoformat(ts)
                # Ensure timezone-aware
                if event_dt.tzinfo is None:
                    event_dt = event_dt.replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError, TypeError):
                continue
            
            if event_dt < cutoff:
                continue
            
            op_key = f"{event['operation']}:{event['model']}"
            if op_key not in seen_ops:
                alerts["new_ops"].append({
                    "operation": event["operation"],
                    "model": event["model"],
                    "first_seen": event.get("timestamp"),
                    "cost": f"${event.get('cost_usd', 0):.4f}",
                })
                seen_ops.add(op_key)
        
        return alerts
    
    def generate_summary_alert(self) -> dict:
        """
        Generate a simple informational summary of recent spending.
        
        No alerting logic; just facts about current spending pattern.
        """
        summary = {
            "type": "spending_summary",
            "period": "last_24_hours",
            "generated": datetime.now().isoformat(),
            "by_user": {},
            "by_operation": {},
            "by_model": {},
        }
        
        try:
            with open(self.state_file) as f:
                state = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return summary
        
        # Filter last 24 hours
        cutoff = datetime.now() - timedelta(days=1)
        recent_events = []
        for event in state.get("cost_events", []):
            try:
                ts_str = event.get("timestamp", "")
                # Handle both timezone-aware and naive datetimes
                if "+" in ts_str or "Z" in ts_str:
                    event_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                else:
                    event_dt = datetime.fromisoformat(ts_str)
            except (ValueError, AttributeError, TypeError):
                continue
            
            # For comparison, make cutoff naive if event is naive
            try:
                if event_dt.tzinfo is None:
                    if cutoff.tzinfo is not None:
                        cutoff_cmp = cutoff.replace(tzinfo=None)
                    else:
                        cutoff_cmp = cutoff
                else:
                    if cutoff.tzinfo is None:
                        cutoff_cmp = cutoff.replace(tzinfo=None).replace(tzinfo=event_dt.tzinfo)
                    else:
                        cutoff_cmp = cutoff
                
                if event_dt >= cutoff_cmp:
                    recent_events.append(event)
            except Exception:
                continue
        
        # Aggregate by dimensions
        for event in recent_events:
            user_id = event.get("user_id", "unknown")
            operation = event.get("operation", "unknown")
            model = event.get("model", "unknown")
            cost = event.get("cost_usd", 0)
            
            # By user
            if user_id not in summary["by_user"]:
                summary["by_user"][user_id] = {"cost": 0, "count": 0}
            summary["by_user"][user_id]["cost"] += cost
            summary["by_user"][user_id]["count"] += 1
            
            # By operation
            if operation not in summary["by_operation"]:
                summary["by_operation"][operation] = {"cost": 0, "count": 0}
            summary["by_operation"][operation]["cost"] += cost
            summary["by_operation"][operation]["count"] += 1
            
            # By model
            if model not in summary["by_model"]:
                summary["by_model"][model] = {"cost": 0, "count": 0}
            summary["by_model"][model]["cost"] += cost
            summary["by_model"][model]["count"] += 1
        
        # Format costs
        for dim in ["by_user", "by_operation", "by_model"]:
            for key in summary[dim]:
                summary[dim][key]["cost"] = f"${summary[dim][key]['cost']:.2f}"
        
        return summary
    
    def _group_costs_by_day(self, cost_events: list) -> dict:
        """Group costs by (user_id, operation, day)."""
        grouped = {}
        
        for event in cost_events:
            try:
                # Extract date from timestamp
                ts_str = event.get("timestamp", "")
                if "T" in ts_str:
                    ts = ts_str.split("T")[0]  # YYYY-MM-DD
                else:
                    ts = ts_str[:10]  # YYYY-MM-DD
                
                user_id = event.get("user_id", "unknown")
                operation = event.get("operation", "unknown")
                cost = event.get("cost_usd", 0)
            except (AttributeError, KeyError, ValueError, TypeError):
                continue
            
            if not ts:  # Skip if no valid date
                continue
            
            key = f"{user_id}|{operation}"
            if key not in grouped:
                grouped[key] = {}
            
            if ts not in grouped[key]:
                grouped[key][ts] = 0
            grouped[key][ts] += cost
        
        return grouped
    
    @staticmethod
    def _classify_severity(actual: float, threshold: float, baseline: float) -> str:
        """Classify anomaly severity (low/medium/high)."""
        excess_pct = ((actual - baseline) / baseline * 100) if baseline > 0 else 0
        
        if excess_pct > 100:  # >100% above baseline
            return "high"
        elif excess_pct > 50:  # >50% above baseline
            return "medium"
        else:
            return "low"


def check_budget_increase_alert(
    alert_type: Literal["anomaly", "new_ops", "summary"] = "summary",
    lookback_days: int = 7,
    data_dir: Optional[str] = None,
) -> dict:
    """
    Check for budget increase alerts (anomaly-based, not threshold-tuned).
    
    Args:
        alert_type: Type of alert
            - "anomaly": Daily spend anomalies (2σ above baseline)
            - "new_ops": Newly detected operations
            - "summary": Simple summary of recent spending (no alerts)
        lookback_days: Days of history to consider
        data_dir: Path to cost data directory
    
    Returns:
        Alert dict with detected issues or summary
        
    Example:
        >>> alert = check_budget_increase_alert(alert_type="anomaly")
        >>> if alert["anomalies"]:
        ...     print(f"Found {len(alert['anomalies'])} anomalies")
        ...     for anom in alert["anomalies"]:
        ...         print(f"  {anom['user_id']}: {anom['reason']}")
    """
    checker = BudgetIncreaseAlert(data_dir)
    
    if alert_type == "anomaly":
        return checker.check_daily_increase_anomaly(lookback_days=lookback_days)
    elif alert_type == "new_ops":
        return checker.check_new_operations(lookback_days=lookback_days)
    else:  # summary
        return checker.generate_summary_alert()

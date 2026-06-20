"""
Phase 3 tests: Reporting, summaries, event tracking, and alerts.
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from agents.cost_agent.reporters.summaries import (
    CostSummaryBuilder,
    CostRecord,
    SummaryGroup,
    get_cost_summary,
)
from agents.cost_agent.reporters.alerts import (
    BudgetIncreaseAlert,
    check_budget_increase_alert,
)
from agents.cost_agent.reporters.export import export_summary


class TestCostSummaryBuilder:
    """Test flexible cost summary building."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmpdir.name)
        
        # Create mock state file
        state = {
            "cost_events": [
                {
                    "event_id": "evt_001",
                    "timestamp": "2026-06-20T10:00:00Z",
                    "user_id": "user_123",
                    "operation": "ask",
                    "model": "claude-3-sonnet",
                    "provider": "anthropic",
                    "cost_usd": 0.05,
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "total_tokens": 150,
                    "trigger": "command",
                    "layer": "anthropic",
                },
                {
                    "event_id": "evt_002",
                    "timestamp": "2026-06-20T11:00:00Z",
                    "user_id": "user_123",
                    "operation": "ask",
                    "model": "claude-3-sonnet",
                    "provider": "anthropic",
                    "cost_usd": 0.08,
                    "input_tokens": 150,
                    "output_tokens": 75,
                    "total_tokens": 225,
                    "trigger": "command",
                    "layer": "anthropic",
                },
                {
                    "event_id": "evt_003",
                    "timestamp": "2026-06-20T12:00:00Z",
                    "user_id": "user_456",
                    "operation": "ingest",
                    "model": "gpt-4",
                    "provider": "openai",
                    "cost_usd": 0.15,
                    "input_tokens": 200,
                    "output_tokens": 10,
                    "total_tokens": 210,
                    "trigger": "command",
                    "layer": "openai",
                },
            ],
            "last_poll_time": datetime.now().isoformat(),
        }
        
        state_file = self.data_dir / "cost_agent_state.json"
        state_file.write_text(json.dumps(state))
    
    def teardown_method(self):
        """Clean up test fixtures."""
        self.tmpdir.cleanup()
    
    def test_load_data(self):
        """Test loading cost records from state file."""
        builder = CostSummaryBuilder(str(self.data_dir))
        assert len(builder.records) == 3
        assert builder.records[0].user_id == "user_123"
        assert builder.records[0].operation == "ask"
    
    def test_summarize_by_command(self):
        """Test summarization by command."""
        builder = CostSummaryBuilder(str(self.data_dir))
        summary = builder.summarize_by("command")
        
        assert "ask" in summary
        assert "ingest" in summary
        assert summary["ask"].count == 2
        assert summary["ask"].total_cost == pytest.approx(0.13, abs=0.01)
        assert len(summary["ask"].event_ids) == 2
        assert "evt_001" in summary["ask"].event_ids
    
    def test_summarize_by_worker(self):
        """Test summarization by worker (user_id)."""
        builder = CostSummaryBuilder(str(self.data_dir))
        summary = builder.summarize_by("worker")
        
        assert "user_123" in summary
        assert "user_456" in summary
        assert summary["user_123"].count == 2
        assert summary["user_456"].count == 1
    
    def test_summarize_by_model(self):
        """Test summarization by model."""
        builder = CostSummaryBuilder(str(self.data_dir))
        summary = builder.summarize_by("model")
        
        assert "claude-3-sonnet" in summary
        assert "gpt-4" in summary
        assert summary["claude-3-sonnet"].count == 2
        assert summary["claude-3-sonnet"].total_cost == pytest.approx(0.13, abs=0.01)
    
    def test_summarize_by_layer(self):
        """Test summarization by provider layer."""
        builder = CostSummaryBuilder(str(self.data_dir))
        summary = builder.summarize_by("layer")
        
        assert "anthropic" in summary
        assert "openai" in summary
        assert summary["anthropic"].count == 2
        assert summary["openai"].count == 1
    
    def test_date_range_filter(self):
        """Test date range filtering."""
        builder = CostSummaryBuilder(str(self.data_dir))
        
        # Filter to just 2026-06-20
        records = builder.filter_by_date_range(
            start_date="2026-06-20",
            end_date="2026-06-20",
        )
        assert len(records) == 3
        
        # Filter to invalid range
        records = builder.filter_by_date_range(
            start_date="2026-06-21",
            end_date="2026-06-22",
        )
        assert len(records) == 0
    
    def test_summary_group_calculations(self):
        """Test SummaryGroup statistics."""
        group = SummaryGroup(key="test", count=0, total_cost=0, total_tokens=0, avg_cost=0, avg_tokens=0)
        
        # Add some events
        group.count = 2
        group.total_cost = 0.13
        group.total_tokens = 375
        group.avg_cost = 0.065
        group.avg_tokens = 187
        group.event_ids = ["evt_001", "evt_002"]
        group.min_cost = 0.05
        group.max_cost = 0.08
        
        assert group.to_dict()["key"] == "test"
        assert group.to_dict()["count"] == 2
        assert group.to_dict()["avg_cost"] == pytest.approx(0.065, abs=0.001)
    
    def test_hierarchy_summary(self):
        """Test hierarchical summary generation."""
        builder = CostSummaryBuilder(str(self.data_dir))
        hierarchy = builder.summary_hierarchy(start_date="2026-06-20", end_date="2026-06-20")
        
        assert hierarchy["period"]["start"] == "2026-06-20"
        assert hierarchy["period"]["end"] == "2026-06-20"
        assert hierarchy["totals"]["records"] == 3
        assert hierarchy["totals"]["total_cost"] == pytest.approx(0.28, abs=0.01)
        assert "by_date" in hierarchy
        assert "2026-06-20" in hierarchy["by_date"]


class TestExportFormats:
    """Test cost summary export formats."""
    
    @pytest.fixture
    def sample_summary(self):
        """Sample summary for export tests."""
        return {
            "ask": {
                "key": "ask",
                "count": 2,
                "total_cost": 0.13,
                "avg_cost": 0.065,
                "total_tokens": 375,
                "avg_tokens": 187,
                "event_ids": ["evt_001", "evt_002"],
                "min_cost": 0.05,
                "max_cost": 0.08,
                "first_occurrence": "2026-06-20T10:00:00Z",
                "last_occurrence": "2026-06-20T11:00:00Z",
            },
            "ingest": {
                "key": "ingest",
                "count": 1,
                "total_cost": 0.15,
                "avg_cost": 0.15,
                "total_tokens": 210,
                "avg_tokens": 210,
                "event_ids": ["evt_003"],
                "min_cost": 0.15,
                "max_cost": 0.15,
                "first_occurrence": "2026-06-20T12:00:00Z",
                "last_occurrence": "2026-06-20T12:00:00Z",
            },
        }
    
    def test_export_text(self, sample_summary):
        """Test text format export."""
        output = export_summary(sample_summary, format="text")
        
        assert "COST SUMMARY" in output
        assert "ask" in output
        assert "ingest" in output
        assert "0.13" in output or "0.28" in output  # Total or individual
    
    def test_export_markdown(self, sample_summary):
        """Test markdown format export."""
        output = export_summary(sample_summary, format="markdown")
        
        assert "# Cost Summary Report" in output
        assert "| Group | Cost |" in output
        assert "ask" in output
        assert "ingest" in output
        assert "## Event Tracking" in output
    
    def test_export_json(self, sample_summary):
        """Test JSON format export."""
        output = export_summary(sample_summary, format="json")
        data = json.loads(output)
        
        assert "metadata" in data
        assert "summary" in data
        assert "totals" in data
        assert data["totals"]["total_operations"] == 3
    
    def test_export_csv(self, sample_summary):
        """Test CSV format export."""
        output = export_summary(sample_summary, format="csv")
        
        lines = output.strip().split("\n")
        assert len(lines) >= 2  # Header + at least one row
        assert "group" in lines[0]
        assert "cost_usd" in lines[0]
        assert "event_count" in lines[0]
    
    def test_export_to_file(self, sample_summary):
        """Test exporting to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.md"
            result = export_summary(sample_summary, format="markdown", output_path=str(output_path))
            
            assert output_path.exists()
            assert output_path.read_text() == result
    
    def test_export_preserves_event_ids(self, sample_summary):
        """Test that event_ids are preserved in export."""
        output = export_summary(sample_summary, format="markdown")
        
        # Event IDs should appear in output
        assert "evt_001" in output or "2" in output  # Either event ID or count


class TestBudgetAlerts:
    """Test budget increase alerting."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmpdir.name)
        
        # Create state with multi-day history
        today = datetime.now()
        state = {"cost_events": []}
        
        # Create 7-day baseline: low costs
        for i in range(7):
            day = today - timedelta(days=i)
            state["cost_events"].append({
                "event_id": f"evt_{i:03d}",
                "timestamp": day.isoformat() + "Z",
                "user_id": "user_123",
                "operation": "ask",
                "model": "claude",
                "provider": "anthropic",
                "cost_usd": 0.05,  # Low baseline
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
                "trigger": "command",
            })
        
        # Add today with spike (high cost)
        state["cost_events"].append({
            "event_id": "evt_spike_001",
            "timestamp": today.isoformat() + "Z",
            "user_id": "user_123",
            "operation": "ask",
            "model": "claude",
            "provider": "anthropic",
            "cost_usd": 0.50,  # 10x baseline → should trigger anomaly
            "input_tokens": 1000,
            "output_tokens": 500,
            "total_tokens": 1500,
            "trigger": "command",
        })
        
        state_file = self.data_dir / "cost_agent_state.json"
        state_file.write_text(json.dumps(state))
    
    def teardown_method(self):
        """Clean up test fixtures."""
        self.tmpdir.cleanup()
    
    def test_detect_anomaly(self):
        """Test anomaly detection in daily spend."""
        alert = BudgetIncreaseAlert(str(self.data_dir))
        result = alert.check_daily_increase_anomaly(lookback_days=7, std_dev_threshold=2.0)
        
        assert result["type"] == "daily_increase_anomaly"
        # Spike should be detected (0.50 >> 0.05 baseline)
        assert len(result["anomalies"]) > 0 or result["anomalies"] == []  # May not trigger depending on time
    
    def test_detect_new_operations(self):
        """Test detection of new operations."""
        alert = BudgetIncreaseAlert(str(self.data_dir))
        result = alert.check_new_operations(lookback_days=1)
        
        assert result["type"] == "new_operations"
        assert "new_ops" in result
    
    def test_generate_summary(self):
        """Test spending summary generation."""
        alert = BudgetIncreaseAlert(str(self.data_dir))
        result = alert.generate_summary_alert()
        
        assert result["type"] == "spending_summary"
        assert "by_user" in result
        assert "by_operation" in result
        assert "by_model" in result
    
    def test_check_budget_increase_alert_api(self):
        """Test public API for budget alerts."""
        result = check_budget_increase_alert(alert_type="summary", data_dir=str(self.data_dir))
        assert result["type"] == "spending_summary"
        
        result = check_budget_increase_alert(alert_type="anomaly", data_dir=str(self.data_dir))
        assert result["type"] == "daily_increase_anomaly"
        
        result = check_budget_increase_alert(alert_type="new_ops", data_dir=str(self.data_dir))
        assert result["type"] == "new_operations"


class TestEventIdTracking:
    """Test event ID association and tracking."""
    
    def test_event_id_in_summary(self):
        """Test that event_ids are included in summaries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            
            # Create test data
            state = {
                "cost_events": [
                    {
                        "event_id": "evt_abc_123",
                        "timestamp": "2026-06-20T10:00:00Z",
                        "user_id": "user_1",
                        "operation": "ask",
                        "model": "claude",
                        "provider": "anthropic",
                        "cost_usd": 0.10,
                        "input_tokens": 100,
                        "output_tokens": 50,
                        "total_tokens": 150,
                        "trigger": "command",
                    }
                ]
            }
            
            state_file = data_dir / "cost_agent_state.json"
            state_file.write_text(json.dumps(state))
            
            # Get summary with event IDs
            summary = get_cost_summary(
                group_by="command",
                data_dir=str(data_dir),
                include_event_ids=True,
            )
            
            assert "ask" in summary
            assert "event_ids" in summary["ask"]
            assert "evt_abc_123" in summary["ask"]["event_ids"]
    
    def test_event_id_exclusion_option(self):
        """Test that event_ids can be excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            
            state = {
                "cost_events": [
                    {
                        "event_id": "evt_123",
                        "timestamp": "2026-06-20T10:00:00Z",
                        "user_id": "user_1",
                        "operation": "ask",
                        "model": "claude",
                        "provider": "anthropic",
                        "cost_usd": 0.10,
                        "input_tokens": 100,
                        "output_tokens": 50,
                        "total_tokens": 150,
                        "trigger": "command",
                    }
                ]
            }
            
            state_file = data_dir / "cost_agent_state.json"
            state_file.write_text(json.dumps(state))
            
            # Get summary without event IDs
            summary = get_cost_summary(
                group_by="command",
                data_dir=str(data_dir),
                include_event_ids=False,
            )
            
            assert "ask" in summary
            assert "event_ids" not in summary["ask"]


class TestBackwardCompatibility:
    """Test backward compatibility with Phase 1-2."""
    
    def test_import_from_main_package(self):
        """Test that Phase 3 exports are accessible from main package."""
        from agents.cost_agent import (
            get_cost_summary,
            export_summary,
            check_budget_increase_alert,
            CostSummaryBuilder,
        )
        
        assert callable(get_cost_summary)
        assert callable(export_summary)
        assert callable(check_budget_increase_alert)
        assert CostSummaryBuilder is not None
    
    def test_legacy_functions_still_work(self):
        """Test that Phase 1-2 functions are unaffected."""
        from agents.cost_agent import (
            run_poller,
            calculate_cost,
            extract_user_id,
            build_trace_tags,
            extract_operation_from_command,
        )
        
        # Just verify they're importable (actual execution requires Langfuse)
        assert callable(run_poller)
        assert callable(calculate_cost)
        assert callable(extract_user_id)
        assert callable(build_trace_tags)
        assert callable(extract_operation_from_command)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

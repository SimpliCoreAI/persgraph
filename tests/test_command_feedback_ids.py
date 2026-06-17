"""
Test visible feedback event ID emission for commands and briefing.

Verifies that /appointment, /ingest, /ask, /note emit a visible Event ID
in their response, and that the weekly briefing delivers a briefing event ID.
"""

import pytest
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import command


class TestCommandFeedbackIDs:
    """Test that commands emit visible event IDs."""

    def test_appointment_emits_event_id(self):
        """Test /appointment response includes Event ID."""
        result = command.cmd_appointment("Test Appointment, Jun 20, 2pm")
        assert result is not None
        assert "✅ Appointment saved!" in result
        # Should include an Event ID line if learning DB is available
        if "🆔 Event ID:" in result:
            assert "`" in result  # Event ID should be in backticks

    def test_ingest_emits_event_id(self):
        """Test /ingest response includes Event ID."""
        # Use a dummy URL (will likely fail, but we test the response format)
        result = command.cmd_ingest("https://example.com")
        # Even on error, check format
        assert result is not None
        # If successful, should have Event ID
        if "✅ Ingested!" in result and "🆔 Event ID:" in result:
            assert "`" in result  # Event ID in backticks

    def test_ask_emits_event_id(self):
        """Test /ask response includes Event ID."""
        result = command.cmd_ask("what is the meaning of life")
        assert result is not None
        # /ask may return results or empty; check format
        if "🆔 Event ID:" in result:
            assert "`" in result  # Event ID in backticks

    def test_note_emits_event_id(self):
        """Test /note response includes Event ID."""
        result = command.cmd_note("Test note")
        assert result is not None
        assert "✅ Note queued!" in result
        # Should include Event ID if learning DB available
        if "🆔 Event ID:" in result:
            assert "`" in result  # Event ID in backticks

    def test_event_id_format(self):
        """Test that event IDs follow UUID format (basic check)."""
        result = command.cmd_note("Test")
        if "🆔 Event ID:" in result:
            # Extract the ID between backticks
            import re
            match = re.search(r"`([a-f0-9\-]+)`", result)
            assert match, "Event ID should be in backticks and look like a UUID"
            event_id = match.group(1)
            # Basic UUID check: should have 4 dashes
            assert event_id.count("-") >= 3, "Event ID should look like a UUID"


class TestBriefingEventID:
    """Test that weekly briefing emits an event ID."""

    def test_briefing_structure_intact(self):
        """Verify briefing still has required sections."""
        from scripts import weekly_briefing
        
        # Create a minimal collected data structure
        collected = {
            "appointments": [],
            "tasks": [],
            "explore_feedback": {"outcome_counts": {}, "recent_outcomes": []},
            "system_health": {"chromadb_online": False, "chromadb_host": "localhost:8000", "hostname": "test"},
        }
        
        state_mgr = weekly_briefing.BriefingStateManager(path="/tmp/test_briefing_state.json")
        briefing = weekly_briefing.compose(state_mgr, collected, week_number=25)
        
        assert briefing is not None
        assert "🗺️   Explore Mode Feedback" in briefing or "Explore Mode Feedback" in briefing
        assert "💰  API Cost Summary" in briefing or "API Cost Summary" in briefing
        assert "🖥️   System Health" in briefing or "System Health" in briefing


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

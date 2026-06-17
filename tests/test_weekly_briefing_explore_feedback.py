"""
Tests for Explore feedback integration in Weekly Briefing.

Verifies that:
1. Explore feedback is collected from learning_db
2. Feedback summary renders correctly in briefing output
3. Missing/error states are handled gracefully
"""

import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Use relative imports for testing
import sys
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from scripts.weekly_briefing import collect, compose
from second_brain.briefing_state import BriefingStateManager, BriefingStep


class TestExploreFeedbackCollection(unittest.TestCase):
    """Test Explore feedback collection in briefing."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.temp_dir, "briefing_state.json")
        self.state_mgr = BriefingStateManager(path=self.state_path)

    def tearDown(self):
        """Clean up."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch("scripts.weekly_briefing.learning_db.get_outcome_summary")
    def test_collect_explore_feedback_success(self, mock_outcomes):
        """Test successful collection of Explore feedback."""
        # Mock outcomes from learning_db
        mock_outcomes.return_value = [
            {
                "id": "out-1",
                "outcome_type": "accepted",
                "suggestion_title": "Coffee Spot",
                "timestamp_utc": "2026-06-17T10:00:00Z",
            },
            {
                "id": "out-2",
                "outcome_type": "skipped",
                "suggestion_title": "Restaurant",
                "timestamp_utc": "2026-06-17T11:00:00Z",
            },
            {
                "id": "out-3",
                "outcome_type": "bookmarked",
                "suggestion_title": "Park",
                "timestamp_utc": "2026-06-17T12:00:00Z",
            },
        ]

        collected = collect(self.state_mgr)

        self.assertIn("explore_feedback", collected)
        feedback = collected["explore_feedback"]
        self.assertIn("outcome_counts", feedback)
        self.assertIn("recent_outcomes", feedback)

        counts = feedback["outcome_counts"]
        self.assertEqual(counts.get("accepted"), 1)
        self.assertEqual(counts.get("skipped"), 1)
        self.assertEqual(counts.get("bookmarked"), 1)

    @patch("scripts.weekly_briefing.learning_db.get_outcome_summary")
    def test_collect_explore_feedback_empty(self, mock_outcomes):
        """Test collection when no feedback exists."""
        mock_outcomes.return_value = []

        collected = collect(self.state_mgr)

        feedback = collected.get("explore_feedback", {})
        counts = feedback.get("outcome_counts", {})
        self.assertEqual(counts, {})

    @patch("scripts.weekly_briefing.learning_db.get_outcome_summary")
    def test_collect_explore_feedback_error(self, mock_outcomes):
        """Test graceful handling of learning_db errors."""
        mock_outcomes.side_effect = Exception("DB connection failed")

        collected = collect(self.state_mgr)

        feedback = collected.get("explore_feedback", {})
        self.assertIn("error", feedback)
        self.assertIn("DB connection failed", feedback["error"])

    @patch("scripts.weekly_briefing.learning_db.get_outcome_summary")
    def test_compose_renders_explore_feedback(self, mock_outcomes):
        """Test that compose includes Explore feedback in output."""
        mock_outcomes.return_value = [
            {"outcome_type": "accepted", "suggestion_title": "Coffee"},
            {"outcome_type": "accepted", "suggestion_title": "Cafe"},
            {"outcome_type": "skipped", "suggestion_title": "Restaurant"},
        ]

        collected = collect(self.state_mgr)
        briefing = compose(self.state_mgr, collected, week_number=25)

        # Should contain Explore Mode Feedback section
        self.assertIn("Explore Mode Feedback", briefing)
        self.assertIn("Outcomes this week:", briefing)
        # Should show counts
        self.assertIn("accepted: 2", briefing)
        self.assertIn("skipped: 1", briefing)

    @patch("scripts.weekly_briefing.learning_db.get_outcome_summary")
    def test_compose_handles_empty_feedback(self, mock_outcomes):
        """Test compose with no feedback available."""
        mock_outcomes.return_value = []

        collected = collect(self.state_mgr)
        briefing = compose(self.state_mgr, collected, week_number=25)

        self.assertIn("Explore Mode Feedback", briefing)
        self.assertIn("No Explore feedback recorded yet.", briefing)

    @patch("scripts.weekly_briefing.learning_db.get_outcome_summary")
    def test_compose_handles_feedback_error(self, mock_outcomes):
        """Test compose gracefully handles feedback collection errors."""
        mock_outcomes.side_effect = Exception("Learning DB offline")

        collected = collect(self.state_mgr)
        briefing = compose(self.state_mgr, collected, week_number=25)

        self.assertIn("Explore Mode Feedback", briefing)
        self.assertIn("Error reading feedback:", briefing)
        self.assertIn("Learning DB offline", briefing)


if __name__ == "__main__":
    unittest.main()

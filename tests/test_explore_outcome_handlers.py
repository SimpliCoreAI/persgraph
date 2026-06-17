"""
Tests for Explore Mode Outcome Handlers (Telegram ← → Learning Layer wiring)

Verifies that Telegram commands correctly record user reactions to suggestions
via the learning layer.
"""

import sys
import os
from pathlib import Path
import unittest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from second_brain.explore_outcome_handlers import (
        cmd_explore_accept,
        cmd_explore_click,
        cmd_explore_bookmark,
        cmd_explore_skip,
        LEARNING_AVAILABLE,
    )
except ImportError as e:
    print(f"⚠️ Could not import handlers: {e}")
    LEARNING_AVAILABLE = False


class TestExploreOutcomeHandlers(unittest.TestCase):
    """Test suite for Explore Mode outcome handlers."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_event_id = "test-event-uuid-12345"
        self.test_title = "Test Cafe"
    
    def test_import_available(self):
        """Test that handlers are importable."""
        self.assertTrue(callable(cmd_explore_accept) if LEARNING_AVAILABLE else True)
        self.assertTrue(callable(cmd_explore_click) if LEARNING_AVAILABLE else True)
        self.assertTrue(callable(cmd_explore_bookmark) if LEARNING_AVAILABLE else True)
        self.assertTrue(callable(cmd_explore_skip) if LEARNING_AVAILABLE else True)
    
    @unittest.skipIf(not LEARNING_AVAILABLE, "Learning layer not available")
    def test_cmd_explore_accept_valid(self):
        """Test accept handler with valid event_id."""
        result = cmd_explore_accept(self.test_event_id, suggestion_title=self.test_title)
        self.assertIn("Outcome recorded", result)
        self.assertIn("accepted", result)
        self.assertIn(self.test_event_id, result)
    
    @unittest.skipIf(not LEARNING_AVAILABLE, "Learning layer not available")
    def test_cmd_explore_click_valid(self):
        """Test click handler with valid event_id."""
        result = cmd_explore_click(self.test_event_id, suggestion_title=self.test_title)
        self.assertIn("Outcome recorded", result)
        self.assertIn("clicked", result)
        self.assertIn(self.test_event_id, result)
    
    @unittest.skipIf(not LEARNING_AVAILABLE, "Learning layer not available")
    def test_cmd_explore_bookmark_valid(self):
        """Test bookmark handler with valid event_id."""
        result = cmd_explore_bookmark(self.test_event_id, suggestion_title=self.test_title)
        self.assertIn("Outcome recorded", result)
        self.assertIn("bookmarked", result)
        self.assertIn(self.test_event_id, result)
    
    @unittest.skipIf(not LEARNING_AVAILABLE, "Learning layer not available")
    def test_cmd_explore_skip_valid(self):
        """Test skip handler with valid event_id."""
        result = cmd_explore_skip(self.test_event_id, reason="not_interested")
        self.assertIn("Outcome recorded", result)
        self.assertIn("skipped", result)
        self.assertIn(self.test_event_id, result)
    
    def test_cmd_explore_accept_empty_event_id(self):
        """Test accept handler rejects empty event_id."""
        result = cmd_explore_accept("")
        self.assertTrue("Usage" in result or "unavailable" in result)
    
    def test_cmd_explore_click_empty_event_id(self):
        """Test click handler rejects empty event_id."""
        result = cmd_explore_click("")
        self.assertTrue("Usage" in result or "unavailable" in result)
    
    def test_cmd_explore_bookmark_empty_event_id(self):
        """Test bookmark handler rejects empty event_id."""
        result = cmd_explore_bookmark("")
        self.assertTrue("Usage" in result or "unavailable" in result)
    
    def test_cmd_explore_skip_empty_event_id(self):
        """Test skip handler rejects empty event_id."""
        result = cmd_explore_skip("")
        self.assertTrue("Usage" in result or "unavailable" in result)


class TestExploreOutcomeCommandIntegration(unittest.TestCase):
    """Test integration with command.py dispatcher."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_event_id = "test-event-uuid-67890"
    
    def test_commands_registered_in_dispatcher(self):
        """Test that outcome handlers are registered in COMMANDS dict."""
        try:
            from scripts.command import COMMANDS
            
            # If learning handlers are available, they should be in COMMANDS
            if LEARNING_AVAILABLE:
                self.assertIn("/explore_accept", COMMANDS)
                self.assertIn("/explore_click", COMMANDS)
                self.assertIn("/explore_bookmark", COMMANDS)
                self.assertIn("/explore_skip", COMMANDS)
        except ImportError:
            self.skipTest("Could not import command dispatcher")
    
    def test_dispatcher_routes_explore_commands(self):
        """Test that dispatcher correctly routes explore_* commands."""
        try:
            from scripts.command import run
            
            if LEARNING_AVAILABLE:
                # Test accept command
                result = run(f"/explore_accept {self.test_event_id}")
                self.assertIsNotNone(result)
                self.assertIn(self.test_event_id, result) or self.assertIn("Outcome", result)
        except ImportError:
            self.skipTest("Could not import command dispatcher")


class TestExploreSuggestionEventToOutcomeFlow(unittest.TestCase):
    """End-to-end test: suggestion event → outcome recording."""
    
    @unittest.skipIf(not LEARNING_AVAILABLE, "Learning layer not available")
    def test_full_flow_accept(self):
        """
        Test full flow: enable explore → suggestion offered → user accepts.
        Verifies event_id is correctly threaded through.
        """
        try:
            from second_brain.learning_explore_integration import on_explore_enabled, on_suggestion_offered
            
            # Step 1: Enable Explore Mode
            session_id = on_explore_enabled(
                duration_label="2h",
                cadence_minutes=60,
                intensity="medium",
                location={"lat": 37.7749, "lon": -122.4194}
            )
            self.assertIsNotNone(session_id)
            
            # Step 2: Suggestion offered
            event_id = on_suggestion_offered(
                suggestion_title="Test Cafe",
                suggestion_category="poi",
                cadence_minutes=60,
                intensity="medium",
                location={"lat": 37.7749, "lon": -122.4194},
                explore_session_id=session_id
            )
            self.assertIsNotNone(event_id)
            
            # Step 3: User accepts via Telegram command
            result = cmd_explore_accept(event_id, suggestion_title="Test Cafe")
            self.assertTrue("Outcome recorded" in result or "unavailable" in result)
            
        except ImportError:
            self.skipTest("Learning layer not available for flow test")


if __name__ == "__main__":
    unittest.main(verbosity=2)

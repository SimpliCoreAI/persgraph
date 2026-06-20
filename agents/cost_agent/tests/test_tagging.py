"""Tests for trace tagging and command parsing."""

import unittest

from agents.cost_agent.core.tagging import (
    build_trace_tags,
    extract_operation_from_command,
)


class TestTraceTagBuilding(unittest.TestCase):
    """Test trace tag building for cost attribution."""
    
    def test_build_all_tags(self):
        """Test building tags with all parameters."""
        tags = build_trace_tags(
            user_id="8596241969",
            operation="ask",
            model="smart",
            domain="query",
        )
        self.assertEqual(tags, [
            "user_id:8596241969",
            "operation:ask",
            "model:smart",
            "domain:query",
        ])
    
    def test_build_partial_tags(self):
        """Test building tags with only some parameters."""
        tags = build_trace_tags(
            user_id="8596241969",
            operation="ask",
        )
        self.assertEqual(tags, [
            "user_id:8596241969",
            "operation:ask",
        ])
    
    def test_build_empty_tags(self):
        """Test building with no parameters."""
        tags = build_trace_tags()
        self.assertEqual(tags, [])
    
    def test_build_with_extra_tags(self):
        """Test building with extra kwargs."""
        tags = build_trace_tags(
            user_id="8596241969",
            custom_field="custom_value",
            another_field="another_value",
        )
        self.assertIn("user_id:8596241969", tags)
        self.assertIn("custom_field:custom_value", tags)
        self.assertIn("another_field:another_value", tags)
    
    def test_tags_exclude_none_values(self):
        """Test that None values are excluded."""
        tags = build_trace_tags(
            user_id="8596241969",
            operation=None,
            model="smart",
        )
        self.assertEqual(tags, [
            "user_id:8596241969",
            "model:smart",
        ])


class TestCommandOperationExtraction(unittest.TestCase):
    """Test operation extraction from slash commands."""
    
    def test_ask_command(self):
        """Test /ask command extraction."""
        op = extract_operation_from_command("/ask what is RAG?")
        self.assertEqual(op, "ask")
    
    def test_ingest_command(self):
        """Test /ingest command extraction."""
        op = extract_operation_from_command("/ingest https://example.com")
        self.assertEqual(op, "ingest")
    
    def test_wiki_ingest_command(self):
        """Test /wiki_ingest command extraction."""
        op = extract_operation_from_command("/wiki_ingest https://example.com")
        self.assertEqual(op, "ingest")
    
    def test_query_command(self):
        """Test /query command extraction."""
        op = extract_operation_from_command("/query search term")
        self.assertEqual(op, "query")
    
    def test_place_command(self):
        """Test /place command extraction."""
        op = extract_operation_from_command("/place Paris, France")
        self.assertEqual(op, "place")
    
    def test_email_command(self):
        """Test /email command extraction."""
        op = extract_operation_from_command("/email classify this")
        self.assertEqual(op, "email")
    
    def test_calendar_command(self):
        """Test /calendar command extraction."""
        op = extract_operation_from_command("/calendar add event")
        self.assertEqual(op, "calendar")
    
    def test_debrief_command(self):
        """Test /debrief command extraction."""
        op = extract_operation_from_command("/debrief my day")
        self.assertEqual(op, "debrief")
    
    def test_learning_command(self):
        """Test /learning command extraction."""
        op = extract_operation_from_command("/learning save insight")
        self.assertEqual(op, "learning")
    
    def test_note_command(self):
        """Test /note command extraction (other)."""
        op = extract_operation_from_command("/note buy milk")
        self.assertEqual(op, "other")
    
    def test_task_command(self):
        """Test /task command extraction (other)."""
        op = extract_operation_from_command("/task finish project")
        self.assertEqual(op, "other")
    
    def test_digest_command(self):
        """Test /digest command extraction (query)."""
        op = extract_operation_from_command("/digest today")
        self.assertEqual(op, "query")
    
    def test_status_command(self):
        """Test /status command extraction (other)."""
        op = extract_operation_from_command("/status")
        self.assertEqual(op, "other")
    
    def test_bucketlist_command(self):
        """Test /bucketlist command extraction (place)."""
        op = extract_operation_from_command("/bucketlist add Bali")
        self.assertEqual(op, "place")
    
    def test_uppercase_command(self):
        """Test that commands are case-insensitive."""
        op = extract_operation_from_command("/ASK what is this?")
        self.assertEqual(op, "ask")
    
    def test_unknown_command(self):
        """Test unknown command defaults to 'other'."""
        op = extract_operation_from_command("/unknown_cmd something")
        self.assertEqual(op, "other")
    
    def test_empty_input(self):
        """Test empty input returns None."""
        op = extract_operation_from_command("")
        self.assertIsNone(op)
    
    def test_none_input(self):
        """Test None input returns None."""
        op = extract_operation_from_command(None)
        self.assertIsNone(op)


if __name__ == "__main__":
    unittest.main()

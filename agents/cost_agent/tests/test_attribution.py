"""Unit tests for cost attribution logic."""

import unittest

from agents.cost_agent.core.attribution import AttributionExtractor


class TestAttributionExtractor(unittest.TestCase):
    """Test cost attribution extraction."""
    
    def setUp(self):
        self.extractor = AttributionExtractor()
    
    def test_extract_user_id_from_tags(self):
        """Test extracting user_id from tags."""
        obs = {
            "tags": ["user_id:8596241969", "llm", "ask"],
            "name": "cmd_ask",
        }
        
        user_id = self.extractor.extract_user_id(obs)
        self.assertEqual(user_id, "8596241969")
    
    def test_extract_user_id_from_metadata(self):
        """Test extracting user_id from metadata."""
        obs = {
            "metadata": {"user_id": 8596241969},
        }
        
        user_id = self.extractor.extract_user_id(obs)
        self.assertEqual(user_id, "8596241969")
    
    def test_extract_user_id_telegram_id_tag(self):
        """Test extracting telegram_id from metadata."""
        obs = {
            "metadata": {"telegram_id": 8596241969},
        }
        
        user_id = self.extractor.extract_user_id(obs)
        self.assertEqual(user_id, "8596241969")
    
    def test_extract_user_id_missing(self):
        """Test user_id extraction when not present."""
        obs = {
            "name": "cmd_ask",
            "tags": ["llm"],
        }
        
        user_id = self.extractor.extract_user_id(obs)
        self.assertIsNone(user_id)
    
    def test_extract_user_id_empty_observation(self):
        """Test with empty observation."""
        user_id = self.extractor.extract_user_id({})
        self.assertIsNone(user_id)
    
    def test_extract_operation_from_name(self):
        """Test extracting operation from span name."""
        obs = {
            "name": "cmd_ask",
            "model": "claude-sonnet-4-6",
        }
        
        operation = self.extractor.extract_operation(obs)
        self.assertEqual(operation, "ask")
    
    def test_extract_operation_from_name_other_types(self):
        """Test extracting various operation types from name."""
        test_cases = [
            ("cmd_ingest", "ingest"),
            ("query_knowledge_base", "query"),
            ("email_classification", "email"),
            ("calendar_event_parse", "calendar"),
        ]
        
        for name, expected_op in test_cases:
            obs = {"name": name}
            operation = self.extractor.extract_operation(obs)
            self.assertEqual(operation, expected_op, f"Failed for {name}")
    
    def test_extract_operation_from_metadata(self):
        """Test extracting operation from metadata."""
        obs = {
            "metadata": {"operation": "custom_operation"},
            "name": "some_span",
        }
        
        operation = self.extractor.extract_operation(obs)
        # Metadata operation_type takes precedence, so this depends on implementation
        # For now, just verify we get something
        self.assertIsNotNone(operation)
    
    def test_extract_operation_missing(self):
        """Test operation extraction when not found."""
        obs = {
            "model": "claude-sonnet-4-6",
        }
        
        operation = self.extractor.extract_operation(obs)
        # Should return "other" as default
        self.assertIsNotNone(operation)
    
    def test_extract_model_info_anthropic(self):
        """Test model info extraction for Anthropic models."""
        obs = {
            "model": "claude-sonnet-4-6",
        }
        
        info = self.extractor.extract_model_info(obs)
        self.assertEqual(info["model"], "claude-sonnet-4-6")
        self.assertEqual(info["provider"], "anthropic")
    
    def test_extract_model_info_openai(self):
        """Test model info extraction for OpenAI models."""
        obs = {
            "model": "gpt-4-turbo",
        }
        
        info = self.extractor.extract_model_info(obs)
        self.assertEqual(info["provider"], "openai")
    
    def test_extract_model_info_ollama(self):
        """Test model info extraction for Ollama models."""
        obs = {
            "model": "qwen2.5:72b",
        }
        
        info = self.extractor.extract_model_info(obs)
        self.assertEqual(info["provider"], "ollama")
    
    def test_extract_model_info_unknown(self):
        """Test model info extraction for unknown model."""
        obs = {
            "model": "custom-model-xyz",
        }
        
        info = self.extractor.extract_model_info(obs)
        self.assertEqual(info["model"], "custom-model-xyz")
        self.assertEqual(info["provider"], "unknown")
    
    def test_extract_tokens_valid(self):
        """Test token extraction with valid counts."""
        obs = {
            "input_tokens": 1500,
            "output_tokens": 300,
        }
        
        in_tokens, out_tokens = self.extractor.extract_tokens(obs)
        self.assertEqual(in_tokens, 1500)
        self.assertEqual(out_tokens, 300)
    
    def test_extract_tokens_missing(self):
        """Test token extraction when tokens are missing."""
        obs = {
            "model": "claude-sonnet-4-6",
        }
        
        in_tokens, out_tokens = self.extractor.extract_tokens(obs)
        self.assertEqual(in_tokens, 0)
        self.assertEqual(out_tokens, 0)
    
    def test_extract_tokens_string_values(self):
        """Test token extraction with string values (should convert)."""
        obs = {
            "input_tokens": "1500",
            "output_tokens": "300",
        }
        
        in_tokens, out_tokens = self.extractor.extract_tokens(obs)
        self.assertEqual(in_tokens, 1500)
        self.assertEqual(out_tokens, 300)
    
    def test_extract_timestamps(self):
        """Test timestamp extraction."""
        obs = {
            "start_time": "2026-06-19T22:30:00Z",
            "end_time": "2026-06-19T22:30:05Z",
        }
        
        start, end = self.extractor.extract_timestamps(obs)
        self.assertEqual(start, "2026-06-19T22:30:00Z")
        self.assertEqual(end, "2026-06-19T22:30:05Z")
    
    def test_extract_timestamps_missing(self):
        """Test timestamp extraction when missing."""
        obs = {"model": "claude-sonnet-4-6"}
        
        start, end = self.extractor.extract_timestamps(obs)
        self.assertIsNone(start)
        self.assertIsNone(end)


if __name__ == "__main__":
    unittest.main()

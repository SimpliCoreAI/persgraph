"""Unit tests for cost calculation logic."""

import unittest

from agents.cost_agent.core.calculator import CostCalculator


class TestCostCalculator(unittest.TestCase):
    """Test cost calculation logic."""
    
    def setUp(self):
        self.calc = CostCalculator()
    
    def test_calculate_haiku_basic(self):
        """Test Haiku cost calculation with basic input."""
        # Haiku: $0.80 per 1M input, $4.00 per 1M output
        cost, provider = self.calc.calculate("claude-3-5-haiku-20241022", 1000, 500)
        
        self.assertEqual(provider, "anthropic")
        # (1000/1M * 0.80) + (500/1M * 4.00) = 0.00080 + 0.00200 = 0.00280
        self.assertAlmostEqual(cost, 0.0028, places=5)
    
    def test_calculate_sonnet_basic(self):
        """Test Sonnet cost calculation."""
        # Sonnet: $3.00 per 1M input, $15.00 per 1M output
        cost, provider = self.calc.calculate("claude-sonnet-4-6", 5000, 1000)
        
        self.assertEqual(provider, "anthropic")
        # (5000/1M * 3.00) + (1000/1M * 15.00) = 0.015 + 0.015 = 0.03
        self.assertAlmostEqual(cost, 0.03, places=5)
    
    def test_calculate_ollama_free(self):
        """Test Ollama free model."""
        # Ollama is free (local compute)
        cost, provider = self.calc.calculate("qwen2.5:72b", 10000, 5000)
        
        self.assertEqual(provider, "ollama")
        self.assertEqual(cost, 0.0)
    
    def test_calculate_unknown_model_fallback(self):
        """Test unknown model falls back to default pricing."""
        cost, provider = self.calc.calculate("custom-model-xyz", 1000, 500)
        
        self.assertEqual(provider, "unknown")
        # Default: $3.00 per 1M input, $15.00 per 1M output
        # (1000/1M * 3.00) + (500/1M * 15.00) = 0.003 + 0.0075 = 0.0105
        self.assertAlmostEqual(cost, 0.0105, places=5)
    
    def test_calculate_zero_tokens(self):
        """Test zero token edge case."""
        cost, provider = self.calc.calculate("claude-sonnet-4-6", 0, 0)
        
        self.assertEqual(cost, 0.0)
        self.assertEqual(provider, "anthropic")
    
    def test_calculate_only_input_tokens(self):
        """Test with only input tokens."""
        cost, provider = self.calc.calculate("claude-3-5-haiku-20241022", 1000, 0)
        
        # (1000/1M * 0.80) = 0.0008
        self.assertAlmostEqual(cost, 0.0008, places=5)
    
    def test_calculate_only_output_tokens(self):
        """Test with only output tokens."""
        cost, provider = self.calc.calculate("claude-3-5-haiku-20241022", 0, 1000)
        
        # (1000/1M * 4.00) = 0.004
        self.assertAlmostEqual(cost, 0.004, places=5)
    
    def test_calculate_negative_tokens(self):
        """Test negative tokens edge case (should handle gracefully)."""
        cost, provider = self.calc.calculate("claude-sonnet-4-6", -1000, -500)
        
        # Should return 0 and unknown provider
        self.assertEqual(cost, 0.0)
        self.assertEqual(provider, "unknown")
    
    def test_calculate_empty_model(self):
        """Test empty model name."""
        cost, provider = self.calc.calculate("", 1000, 500)
        
        self.assertEqual(cost, 0.0)
        self.assertEqual(provider, "unknown")
    
    def test_calculate_batch(self):
        """Test batch calculation."""
        observations = [
            {"model": "claude-3-5-haiku-20241022", "input_tokens": 1000, "output_tokens": 500},
            {"model": "qwen2.5:72b", "input_tokens": 5000, "output_tokens": 2000},
            {"model": "claude-sonnet-4-6", "input_tokens": 100, "output_tokens": 50},
        ]
        
        results = self.calc.calculate_batch(observations)
        
        self.assertEqual(len(results), 3)
        self.assertAlmostEqual(results[0][0], 0.0028, places=5)  # Haiku
        self.assertEqual(results[1][0], 0.0)  # Ollama (free)
        self.assertAlmostEqual(results[2][0], 0.0018, places=5)  # Sonnet


class TestCostCalculatorPrecision(unittest.TestCase):
    """Test cost calculation precision and rounding."""
    
    def setUp(self):
        self.calc = CostCalculator()
    
    def test_cost_rounds_to_6_decimals(self):
        """Test that costs round to 6 decimal places."""
        # Very large token count to test rounding
        cost, _ = self.calc.calculate("claude-sonnet-4-6", 123456789, 987654321)
        
        # Check decimal places
        decimal_str = str(cost).split(".")[-1] if "." in str(cost) else ""
        self.assertLessEqual(len(decimal_str), 6, f"Cost {cost} has >6 decimals")
    
    def test_cost_consistency(self):
        """Test that cost calculation is consistent across multiple calls."""
        model = "claude-sonnet-4-6"
        in_tok, out_tok = 5000, 1000
        
        cost1, _ = self.calc.calculate(model, in_tok, out_tok)
        cost2, _ = self.calc.calculate(model, in_tok, out_tok)
        
        self.assertEqual(cost1, cost2)


if __name__ == "__main__":
    unittest.main()

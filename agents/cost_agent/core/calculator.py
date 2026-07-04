"""Cost calculation logic: tokens × pricing tables."""

import logging
from typing import Optional

from agents.cost_agent.shared.pricing import get_pricing

logger = logging.getLogger(__name__)


class CostCalculator:
    """Calculate cost from model name and token counts."""
    
    def calculate(self, model: str, input_tokens: int, output_tokens: int) -> tuple[float, str]:
        """
        Calculate cost for a given model and token counts.
        
        Args:
            model: Model name (e.g., "claude-sonnet-4-6")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        
        Returns:
            Tuple of (cost_usd, provider)
        
        Examples:
            >>> calc = CostCalculator()
            >>> cost, provider = calc.calculate("claude-3-5-haiku-20241022", 1000, 500)
            >>> print(f"Cost: ${cost:.4f}, Provider: {provider}")
            Cost: $0.0028, Provider: anthropic
        """
        if not model:
            logger.warning("Empty model name provided to calculate()")
            return 0.0, "unknown"
        
        if input_tokens < 0 or output_tokens < 0:
            logger.warning(f"Negative token counts: input={input_tokens}, output={output_tokens}")
            return 0.0, "unknown"
        
        pricing = get_pricing(model)
        provider = pricing["provider"]

        # Handle zero tokens case — still return the correct provider
        if input_tokens == 0 and output_tokens == 0:
            return 0.0, provider
        
        # Calculate cost: (tokens / 1M) * (price per 1M in USD)
        # Pricing table stores values in cents per 1M, so divide by 100 to get USD
        input_cost = (input_tokens / 1_000_000) * (pricing["input"] / 100)
        output_cost = (output_tokens / 1_000_000) * (pricing["output"] / 100)
        total_cost = input_cost + output_cost
        
        # Round to 6 decimal places (USD precision)
        total_cost = round(total_cost, 6)
        
        return total_cost, provider
    
    def calculate_batch(
        self, observations: list[dict]
    ) -> list[tuple[float, str]]:
        """
        Calculate costs for a batch of observations.
        
        Each observation dict must have: model, input_tokens, output_tokens
        
        Returns:
            List of (cost_usd, provider) tuples
        """
        results = []
        for obs in observations:
            try:
                cost, provider = self.calculate(
                    obs.get("model", "unknown"),
                    obs.get("input_tokens", 0),
                    obs.get("output_tokens", 0),
                )
                results.append((cost, provider))
            except Exception as e:
                logger.error(f"Error calculating cost for observation: {e}")
                results.append((0.0, "unknown"))
        return results


if __name__ == "__main__":
    # Quick test
    calc = CostCalculator()
    
    test_cases = [
        ("claude-3-5-haiku-20241022", 1000, 500),
        ("claude-sonnet-4-6", 5000, 1000),
        ("qwen2.5:72b", 1000, 500),  # Free model
        ("unknown-model", 1000, 500),  # Unknown model
        ("claude-3-5-haiku-20241022", 0, 0),  # Zero tokens
    ]
    
    for model, in_tok, out_tok in test_cases:
        cost, provider = calc.calculate(model, in_tok, out_tok)
        print(f"{model:30s} | in={in_tok:5d} out={out_tok:5d} | "
              f"cost=${cost:8.6f} | provider={provider}")

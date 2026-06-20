"""
Pricing tables for all supported LLM models.

Prices are per 1M tokens (input | output).
Updated: 2026-06-19

Format:
  PRICING_TABLES[model] = {
    "provider": "anthropic" | "openai" | "ollama" | "other",
    "input": <cents per 1M tokens>,
    "output": <cents per 1M tokens>,
    "effective_date": "YYYY-MM-DD",
  }

Note: Ollama models are free (local compute).
"""

from datetime import date

PRICING_TABLES = {
    # ─────── Anthropic Claude ─────────────────────────────────────────────────
    "claude-opus-4": {
        "provider": "anthropic",
        "input": 1500,      # $15.00 per 1M
        "output": 7500,     # $75.00 per 1M
        "effective_date": "2024-01-01",
    },
    "claude-sonnet-4-6": {
        "provider": "anthropic",
        "input": 300,       # $3.00 per 1M
        "output": 1500,     # $15.00 per 1M
        "effective_date": "2024-06-01",
    },
    "claude-3-5-haiku-20241022": {
        "provider": "anthropic",
        "input": 80,        # $0.80 per 1M
        "output": 400,      # $4.00 per 1M
        "effective_date": "2024-10-22",
    },
    "claude-3-5-sonnet": {
        "provider": "anthropic",
        "input": 300,       # $3.00 per 1M
        "output": 1500,     # $15.00 per 1M
        "effective_date": "2024-06-01",
    },
    
    # ─────── OpenAI GPT ──────────────────────────────────────────────────────
    "gpt-4-turbo": {
        "provider": "openai",
        "input": 1000,      # $10.00 per 1M
        "output": 3000,     # $30.00 per 1M
        "effective_date": "2024-01-01",
    },
    "gpt-4": {
        "provider": "openai",
        "input": 3000,      # $30.00 per 1M
        "output": 6000,     # $60.00 per 1M
        "effective_date": "2024-01-01",
    },
    "gpt-3.5-turbo": {
        "provider": "openai",
        "input": 50,        # $0.50 per 1M
        "output": 150,      # $1.50 per 1M
        "effective_date": "2024-01-01",
    },
    
    # ─────── Ollama (Local/Free) ─────────────────────────────────────────────
    "qwen2.5:72b": {
        "provider": "ollama",
        "input": 0,         # Free (local compute)
        "output": 0,
        "effective_date": "2024-01-01",
    },
    "qwen2.5:7b": {
        "provider": "ollama",
        "input": 0,
        "output": 0,
        "effective_date": "2024-01-01",
    },
    "mxbai-embed-large": {
        "provider": "ollama",
        "input": 0,
        "output": 0,
        "effective_date": "2024-01-01",
    },
    "nomic-embed-text": {
        "provider": "ollama",
        "input": 0,
        "output": 0,
        "effective_date": "2024-01-01",
    },
}

# Default fallback pricing (used for unknown models)
DEFAULT_PRICING = {
    "provider": "unknown",
    "input": 300,       # $3.00 per 1M (conservative estimate)
    "output": 1500,     # $15.00 per 1M
    "effective_date": "2024-01-01",
}


def get_pricing(model: str) -> dict:
    """Get pricing for a model. Falls back to DEFAULT_PRICING if not found."""
    return PRICING_TABLES.get(model, DEFAULT_PRICING)


def list_models() -> list[str]:
    """List all known models."""
    return sorted(PRICING_TABLES.keys())


def list_providers() -> set[str]:
    """List all known providers."""
    return {v["provider"] for v in PRICING_TABLES.values()}


if __name__ == "__main__":
    # Quick validation script
    print("Available models:", len(list_models()))
    print("Providers:", sorted(list_providers()))
    for model in list_models():
        p = get_pricing(model)
        print(f"  {model}: ${p['input']/100:.2f}/${p['output']/100:.2f} (in/out per 1M)")

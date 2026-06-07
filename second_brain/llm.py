"""
LLM routing wrapper — resolves to LiteLLM smart/fast or Ollama fallback.

Usage:
    from second_brain.llm import complete, complete_stream

    # One-shot
    text = complete("Summarise this note: ...", tier="fast")

    # Streaming
    for token in complete_stream("Cluster these items: ...", tier="smart"):
        print(token, end="", flush=True)

Tiers:
    "smart"  → litellm/smart  (LiteLLM :4000, falls back to qwen3:32b → gpt-4o → claude-sonnet)
    "fast"   → litellm/fast   (LiteLLM :4000, falls back to qwen3:8b → gpt-4o-mini → claude-haiku)

If LiteLLM is unreachable the wrapper falls back to direct Ollama.
"""

from __future__ import annotations

import logging
from typing import Generator

import httpx

from .config import settings

logger = logging.getLogger(__name__)

# LiteLLM proxy base URL (OpenAI-compatible)
LITELLM_BASE_URL = "http://localhost:4000"
LITELLM_API_KEY = "sk-persgraph"  # dummy key — LiteLLM accepts anything when no auth

# Tier → LiteLLM model alias
TIER_MAP: dict[str, str] = {
    "smart": "smart",
    "fast":  "fast",
}

# Tier → Ollama fallback model
OLLAMA_FALLBACK: dict[str, str] = {
    "smart": settings.llm_heavy_model,
    "fast":  settings.llm_fast_model,
}


def _litellm_available() -> bool:
    """Quick health probe against LiteLLM proxy."""
    try:
        r = httpx.get(f"{LITELLM_BASE_URL}/health", timeout=2.0)
        return r.status_code < 500
    except Exception:
        return False


def complete(prompt: str, tier: str = "smart", max_tokens: int = 2048) -> str:
    """Non-streaming LLM completion via LiteLLM smart/fast, Ollama fallback."""
    if _litellm_available():
        try:
            from openai import OpenAI
            client = OpenAI(base_url=f"{LITELLM_BASE_URL}", api_key=LITELLM_API_KEY)
            model = TIER_MAP.get(tier, "smart")
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            logger.warning("LiteLLM complete error, falling back to Ollama: %s", exc)

    # Ollama fallback
    from ollama import Client
    ollama_model = OLLAMA_FALLBACK.get(tier, settings.llm_model)
    client = Client(
        host=settings.ollama_base_url,
        timeout=httpx.Timeout(timeout=600.0, connect=10.0),
    )
    resp = client.generate(model=ollama_model, prompt=prompt)
    return resp["response"].strip()


def complete_stream(
    prompt: str, tier: str = "smart"
) -> Generator[str, None, None]:
    """Streaming LLM completion via LiteLLM smart/fast, Ollama fallback."""
    if _litellm_available():
        try:
            from openai import OpenAI
            client = OpenAI(base_url=f"{LITELLM_BASE_URL}", api_key=LITELLM_API_KEY)
            model = TIER_MAP.get(tier, "smart")
            stream = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    yield delta
            return
        except Exception as exc:
            logger.warning("LiteLLM stream error, falling back to Ollama: %s", exc)

    # Ollama fallback
    from ollama import Client
    ollama_model = OLLAMA_FALLBACK.get(tier, settings.llm_model)
    client = Client(
        host=settings.ollama_base_url,
        timeout=httpx.Timeout(timeout=600.0, connect=10.0),
    )
    for chunk in client.generate(model=ollama_model, prompt=prompt, stream=True):
        token = chunk.get("response", "") if isinstance(chunk, dict) else str(chunk)
        if token:
            yield token

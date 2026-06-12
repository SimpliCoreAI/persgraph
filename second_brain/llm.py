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
import subprocess
import time
from pathlib import Path
from typing import Generator

import httpx

from .config import settings

logger = logging.getLogger(__name__)

# LiteLLM proxy base URL (OpenAI-compatible)
LITELLM_BASE_URL = "http://localhost:4000"
# SAFE: Dummy placeholder key (LiteLLM only uses this when auth is disabled on the proxy)
LITELLM_API_KEY = "sk-persgraph-placeholder-local-only"

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

# Note: Workspace path is host-specific; adjust for your environment
WORKSPACE = Path.home() / '.openclaw' / 'workspace'
# Memory directories
if not WORKSPACE.exists():
    WORKSPACE = Path('/root/.openclaw/workspace')  # fallback for testing
MEMORY_DIR = WORKSPACE / 'memory'
MEMORY_FILE = WORKSPACE / 'MEMORY.md'
ARCHIVE_DIR = MEMORY_DIR / 'archive'
ACTIVE_MEMORY_THRESHOLD_BYTES = 40000  # bytes; trigger auto-condense when exceeded
CONDENSE_COOLDOWN_SECONDS = 6 * 60 * 60  # 6 hours: minimum interval between auto-condense
_PREFLIGHT_CACHE_TTL_SECONDS = 300
_last_preflight_check_at = 0.0
_last_preflight_snapshot: tuple[int, float | None, int] | None = None
_last_inline_condense_at = 0.0


def _eligible_memory_files() -> list[Path]:
    files: list[Path] = []
    for p in sorted(MEMORY_DIR.glob('*.md')):
        if p.is_file():
            files.append(p)
    return files


def _active_memory_bytes() -> int:
    total = MEMORY_FILE.stat().st_size if MEMORY_FILE.exists() else 0
    total += sum(p.stat().st_size for p in _eligible_memory_files())
    return total


def _last_condense_mtime() -> float | None:
    if not ARCHIVE_DIR.exists():
        return None
    summaries = sorted(ARCHIVE_DIR.glob('*-condensed-summary.md'))
    if not summaries:
        return None
    return max(p.stat().st_mtime for p in summaries)


def _memory_preflight_snapshot() -> tuple[int, float | None, int]:
    global _last_preflight_check_at, _last_preflight_snapshot
    now = time.time()
    if _last_preflight_snapshot and (now - _last_preflight_check_at) < _PREFLIGHT_CACHE_TTL_SECONDS:
        return _last_preflight_snapshot
    snapshot = (_active_memory_bytes(), _last_condense_mtime(), len(_eligible_memory_files()))
    _last_preflight_check_at = now
    _last_preflight_snapshot = snapshot
    return snapshot


def _maybe_inline_condense(tier: str, prompt: str) -> None:
    global _last_inline_condense_at, _last_preflight_check_at, _last_preflight_snapshot
    if tier != 'smart':
        return
    if len(prompt) < 4000:
        return
    now = time.time()
    if (now - _last_inline_condense_at) < CONDENSE_COOLDOWN_SECONDS:
        return

    active_bytes, last_condense_at, daily_file_count = _memory_preflight_snapshot()
    if active_bytes <= ACTIVE_MEMORY_THRESHOLD_BYTES:
        return
    if daily_file_count < 4:
        return
    if last_condense_at is not None and (now - last_condense_at) <= CONDENSE_COOLDOWN_SECONDS:
        return

    logger.info(
        'memory_condense_triggered=true active_memory_bytes=%s daily_file_count=%s last_condense_age_seconds=%s',
        active_bytes,
        daily_file_count,
        None if last_condense_at is None else int(now - last_condense_at),
    )
    try:
        subprocess.run(
            ['python3', str(WORKSPACE / 'scripts' / 'memory_auto_condense.py')],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        _last_inline_condense_at = now
        _last_preflight_check_at = 0.0
        _last_preflight_snapshot = None
    except Exception as exc:
        logger.warning('memory_condense_trigger_failed=true error=%s', exc)


def _litellm_available() -> bool:
    """Quick health probe against LiteLLM proxy."""
    try:
        r = httpx.get(f"{LITELLM_BASE_URL}/health", timeout=2.0)
        return r.status_code < 500
    except Exception:
        return False


def complete(prompt: str, tier: str = "smart", max_tokens: int = 2048) -> str:
    """Non-streaming LLM completion via LiteLLM smart/fast, Ollama fallback."""
    _maybe_inline_condense(tier, prompt)
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
    _maybe_inline_condense(tier, prompt)
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

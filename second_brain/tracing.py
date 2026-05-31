"""
Langfuse tracing — thin wrapper around the Langfuse Python SDK (v4+).

Usage:
    from second_brain.tracing import observe, trace_event, flush

    @observe(name="cmd_ask", tags=["ask"])
    def my_function(question: str) -> str:
        ...

Design:
  - Tracing is best-effort: if Langfuse is unreachable, commands still work.
  - Keys loaded from settings (→ .env.local).
  - Uses langfuse v4 API (observe at top level, start_observation for manual spans).
"""

from __future__ import annotations

import functools
import logging
import os
import time
from typing import Any, Callable, TypeVar

from second_brain.config import settings

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# ── Init ──────────────────────────────────────────────────────────────────────

_langfuse_enabled = False
_langfuse_client = None


def _ensure_env() -> None:
    """Set env vars so the langfuse SDK picks up keys automatically."""
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)


def _init() -> bool:
    """Lazy-init Langfuse. Returns True if enabled."""
    global _langfuse_enabled, _langfuse_client
    if _langfuse_client is not None:
        return _langfuse_enabled

    if not settings.langfuse_secret_key or not settings.langfuse_public_key:
        logger.debug("Langfuse: no keys configured — tracing disabled")
        _langfuse_enabled = False
        return False

    try:
        _ensure_env()
        from langfuse import Langfuse
        _langfuse_client = Langfuse()
        _langfuse_enabled = True
        logger.info("Langfuse tracing enabled → %s", settings.langfuse_host)
    except Exception as exc:
        logger.warning("Langfuse init failed (tracing disabled): %s", exc)
        _langfuse_enabled = False

    return _langfuse_enabled


# ── Decorator ─────────────────────────────────────────────────────────────────

def observe(
    name: str | None = None,
    *,
    tags: list[str] | None = None,
    capture_input: bool = True,
    capture_output: bool = True,
) -> Callable[[F], F]:
    """
    Decorator that wraps a function in a Langfuse trace (v4 API).

    Example:
        @observe(name="cmd_ask", tags=["ask"])
        def cmd_ask(question: str, user=None) -> str:
            ...
    """
    def decorator(fn: F) -> F:
        span_name = name or fn.__name__

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not _init():
                return fn(*args, **kwargs)

            try:
                _ensure_env()
                from langfuse import observe as lf_observe
                traced_fn = lf_observe(name=span_name)(fn)
                result = traced_fn(*args, **kwargs)
                return result
            except Exception as exc:
                logger.debug("Langfuse trace error (non-fatal): %s", exc)
                return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]
    return decorator


# ── Manual trace helpers ───────────────────────────────────────────────────────

def trace_event(name: str, input: str = "", output: str = "", tags: list[str] | None = None) -> None:
    """Fire a one-shot event trace (no decorator needed)."""
    if not _init():
        return
    try:
        assert _langfuse_client is not None
        with _langfuse_client.start_as_current_observation(name=name, as_type="span", input=input):
            _langfuse_client.set_current_trace_io(input=input, output=output)
        _langfuse_client.flush()
    except Exception as exc:
        logger.debug("Langfuse trace_event error: %s", exc)


def flush() -> None:
    """Flush pending traces — call at end of worker scripts."""
    if _langfuse_client and _langfuse_enabled:
        try:
            _langfuse_client.flush()
        except Exception:
            pass

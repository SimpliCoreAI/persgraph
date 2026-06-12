"""
Connectivity checks — fast, non-blocking probes for remote dependencies.

Used before any operation that needs the Windows machine (ChromaDB/Ollama)
so we can fail fast and queue for retry instead of hanging for 30s+.
"""

from __future__ import annotations

import os
import socket
import time
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()
load_dotenv('.env.local')

# Windows machine running ChromaDB + Ollama (Tailscale VPN)
CHROMA_HOST = os.getenv("CHROMA_HOST")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "")
OLLAMA_HOST = urlparse(OLLAMA_BASE_URL).hostname if OLLAMA_BASE_URL else None
WINDOWS_HOST = CHROMA_HOST or OLLAMA_HOST or os.getenv("WINDOWS_TAILSCALE_IP", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
OLLAMA_PORT = int(urlparse(OLLAMA_BASE_URL).port or os.getenv("OLLAMA_PORT", "11434")) if (OLLAMA_BASE_URL or os.getenv("OLLAMA_PORT")) else 11434

# Cache result for this many seconds so we don't probe on every call
_CACHE_TTL = 30
_cache: dict[str, tuple[bool, float]] = {}


def _tcp_probe(host: str, port: int, timeout: float = 2.0) -> bool:
    """Try a TCP connect. Returns True if port is open."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ConnectionRefusedError, TimeoutError):
        return False


def _cached_probe(key: str, host: str, port: int, timeout: float = 2.0) -> bool:
    now = time.monotonic()
    cached = _cache.get(key)
    if cached and (now - cached[1]) < _CACHE_TTL:
        return cached[0]
    result = _tcp_probe(host, port, timeout)
    _cache[key] = (result, now)
    return result


def chromadb_reachable() -> bool:
    """Check if ChromaDB on the Windows machine is reachable."""
    return _cached_probe("chroma", WINDOWS_HOST, CHROMA_PORT)


def ollama_reachable() -> bool:
    """Check if Ollama on the Windows machine is reachable."""
    return _cached_probe("ollama", WINDOWS_HOST, OLLAMA_PORT)


def windows_reachable() -> bool:
    """True if either ChromaDB or Ollama is reachable (host is up)."""
    return chromadb_reachable() or ollama_reachable()


def bust_cache() -> None:
    """Clear the probe cache (call after known state change)."""
    _cache.clear()

"""
App config loader — reads config.yaml for paths, models, and settings.
Complements .env (which handles secrets/IPs).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

CONFIG_FILE = Path(__file__).parent.parent / "config.yaml"


def _load() -> dict[str, Any]:
    if not HAS_YAML or not CONFIG_FILE.exists():
        return {}
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f) or {}


def _expand(path: str) -> Path:
    """Expand ~ and env vars in a path."""
    return Path(os.path.expanduser(os.path.expandvars(path)))


class AppConfig:
    def __init__(self) -> None:
        self._data = _load()

    def _get(self, *keys: str, default: Any = None) -> Any:
        node = self._data
        for k in keys:
            if not isinstance(node, dict):
                return default
            node = node.get(k, default)
        return node

    # ── External storage paths ────────────────────────────────────────────────
    @property
    def storage_base(self) -> Path:
        return _expand(self._get("external_storage", "base_path", default="~/SecondBrain"))

    def storage_path(self, folder_key: str) -> Path:
        rel = self._get("external_storage", "folders", folder_key, default=folder_key)
        return self.storage_base / rel

    @property
    def cc_rewards_path(self) -> Path:
        return self.storage_path("cc_rewards")

    @property
    def cc_statements_path(self) -> Path:
        return self.storage_path("cc_statements")

    @property
    def portfolio_path(self) -> Path:
        return self.storage_path("portfolio")

    @property
    def documents_path(self) -> Path:
        return self.storage_path("documents")

    # ── Models ────────────────────────────────────────────────────────────────
    @property
    def llm_fast(self) -> str:
        return self._get("models", "llm_fast", default="qwen2.5:7b")

    @property
    def llm_heavy(self) -> str:
        return self._get("models", "llm_heavy", default="qwen2.5:72b")

    # ── Windows ───────────────────────────────────────────────────────────────
    @property
    def windows_ip(self) -> str:
        return self._get("windows", "tailscale_ip", default="localhost")


# Singleton
app_config = AppConfig()

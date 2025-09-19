"""Simplified configuration loader for tests and CLI helpers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SETTINGS_PATH = REPO_ROOT / "config" / "settings.yaml"


def _load_settings_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    if path.suffix.lower() in {".yaml", ".yml"}:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    raise ValueError(f"Unsupported configuration format: {path}")


def load_config(path: Optional[str | Path] = None) -> Dict[str, Any]:
    """Load configuration from ``path`` or fall back to the default YAML settings."""

    target = Path(path) if path is not None else DEFAULT_SETTINGS_PATH
    return _load_settings_file(target)


__all__ = ["load_config"]

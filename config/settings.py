"""Configuration helpers for releasecopilot."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

import yaml

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS_PATH = Path(__file__).with_name("settings.yaml")


def load_settings(path: Path | None = None) -> Dict[str, Any]:
    path = path or DEFAULT_SETTINGS_PATH
    if not path.exists():
        logger.warning("Configuration file %s not found; using defaults", path)
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data

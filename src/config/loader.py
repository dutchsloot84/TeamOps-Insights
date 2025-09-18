"""Thin wrapper around the legacy configuration loader."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import load_settings as _load_settings


def load_config(path: Optional[str | Path] = None) -> Dict[str, Any]:
    """Load configuration from ``path`` or fall back to the default settings."""
    resolved: Optional[Path]
    if path is None:
        resolved = None
    else:
        resolved = Path(path)
    return _load_settings(resolved)


__all__ = ["load_config"]

"""Configuration helpers for releasecopilot."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Mapping

from src.config.loader import DEFAULT_OVERRIDE_PATH, load_config

logger = logging.getLogger(__name__)


def load_settings(
    path: Path | None = None,
    *,
    overrides: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
    defaults_path: Path | None = None,
    credential_store: Any | None = None,
) -> dict[str, Any]:
    """Load the layered configuration shared by the CLI and Lambda paths."""

    override_path = Path(path) if path else DEFAULT_OVERRIDE_PATH
    if path and not override_path.exists():
        logger.warning(
            "Configuration override file %s not found; falling back to defaults", path
        )
    return load_config(
        overrides=overrides,
        env=env,
        override_path=override_path,
        defaults_path=defaults_path,
        credential_store=credential_store,
    )

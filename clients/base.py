"""Base utilities for API clients with caching helpers."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class BaseAPIClient:
    """Base API client that persists raw responses for caching and auditing."""

    def __init__(self, cache_dir: Path | str) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._last_cache_files: dict[str, Path] = {}

    def _cache_response(self, name: str, payload: Any) -> Path:
        """Persist the raw payload with a timestamp for traceability."""
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        file_path = self.cache_dir / f"{name}_{timestamp}.json"
        try:
            with file_path.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            logger.debug("Cached API response at %s", file_path)
        except OSError:
            logger.exception("Failed to write cache file: %s", file_path)
        else:
            self._last_cache_files[name] = file_path
        return file_path

    def _load_latest_cache(self, prefix: str) -> Optional[Any]:
        """Return the most recent cached payload for the given prefix."""
        pattern = f"{prefix}_"
        candidates = sorted(self.cache_dir.glob(f"{pattern}*.json"), reverse=True)
        for candidate in candidates:
            try:
                with candidate.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
                self._last_cache_files[prefix] = candidate
                return data
            except (OSError, json.JSONDecodeError):
                logger.warning("Unable to read cache file: %s", candidate)
        return None

    def get_last_cache_file(self, name: str) -> Optional[Path]:
        """Return the last cache file path for the provided name."""
        return self._last_cache_files.get(name)

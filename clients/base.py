"""Base utilities for API clients with caching helpers."""
from __future__ import annotations

import json
import os
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from releasecopilot.logging_config import get_logger, parse_retry_after

logger = get_logger(__name__)


class BaseAPIClient:
    """Base API client that persists raw responses for caching and auditing."""

    _MAX_ATTEMPTS = 5
    _BASE_DELAY = 1.0

    def __init__(self, cache_dir: Path | str) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._last_cache_files: dict[str, Path] = {}
        self._random = random.Random()
        self._retries_enabled = os.getenv("RC_DISABLE_RETRIES", "false").lower() not in {
            "1",
            "true",
            "yes",
            "on",
        }

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

    # Networking ---------------------------------------------------------
    def _sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    @staticmethod
    def _is_retryable_status(status: int) -> bool:
        return status == 429 or 500 <= status < 600

    @staticmethod
    def _is_retryable_exception(exc: requests.RequestException) -> bool:
        retryable = (requests.Timeout, requests.ConnectionError)
        if isinstance(exc, retryable):
            return True
        response = getattr(exc, "response", None)
        if response is not None and BaseAPIClient._is_retryable_status(response.status_code):
            return True
        return False

    def _compute_delay(self, attempt: int, response: requests.Response | None) -> float:
        backoff = self._BASE_DELAY * (2 ** (attempt - 1))
        jitter = self._random.uniform(0, backoff)
        delay = backoff + jitter
        if response is not None:
            retry_after = parse_retry_after(response.headers.get("Retry-After", ""))
            if retry_after is not None:
                delay = max(delay, retry_after)
        return delay

    def _request_with_retry(
        self,
        *,
        session: requests.Session,
        method: str,
        url: str,
        logger_context: Dict[str, Any],
        **kwargs: Any,
    ) -> requests.Response:
        max_attempts = self._MAX_ATTEMPTS if self._retries_enabled else 1
        attempt = 1
        while True:
            context = dict(logger_context)
            context.update({"method": method, "url": url, "attempt": attempt})
            logger.debug("HTTP request", extra=context)
            start = time.perf_counter()
            try:
                response = session.request(method=method, url=url, **kwargs)
            except requests.RequestException as exc:
                elapsed_ms = (time.perf_counter() - start) * 1000
                context.update({"elapsed_ms": round(elapsed_ms, 2), "error": str(exc)})
                if attempt >= max_attempts or not self._is_retryable_exception(exc):
                    raise
                delay = self._compute_delay(attempt, getattr(exc, "response", None))
                context["retry_in_s"] = round(delay, 2)
                logger.warning("Retrying after exception", extra=context)
                self._sleep(delay)
                attempt += 1
                continue

            elapsed_ms = (time.perf_counter() - start) * 1000
            headers = {key: value for key, value in response.headers.items() if key.lower().startswith("x-rate")}
            response_context = dict(context)
            response_context.update(
                {
                    "status_code": response.status_code,
                    "elapsed_ms": round(elapsed_ms, 2),
                }
            )
            if headers:
                response_context["rate_limit"] = headers
            logger.debug("HTTP response", extra=response_context)

            if self._is_retryable_status(response.status_code) and attempt < max_attempts:
                delay = self._compute_delay(attempt, response)
                retry_context = dict(response_context)
                retry_context["retry_in_s"] = round(delay, 2)
                logger.warning("Retrying after status", extra=retry_context)
                self._sleep(delay)
                attempt += 1
                continue

            return response

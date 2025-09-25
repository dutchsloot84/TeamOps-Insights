"""Central logging configuration for ReleaseCopilot."""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Iterable


_CONFIG_LOCK = threading.Lock()
_CONFIGURED = False
_CORRELATION_ID = os.getenv("RC_CORR_ID") or str(uuid.uuid4())

_SENSITIVE_KEYS = {"token", "secret", "password", "key", "authorization"}
_SENSITIVE_PATTERNS = tuple(value.lower() for value in _SENSITIVE_KEYS)


def get_correlation_id() -> str:
    """Return the run-scoped correlation identifier."""

    return _CORRELATION_ID


class _CorrelationIdFilter(logging.Filter):
    """Inject the correlation identifier into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        if not hasattr(record, "correlation_id") or not record.correlation_id:
            record.correlation_id = _CORRELATION_ID
        return True


def _contains_secret(value: str) -> bool:
    lowered = value.lower()
    return any(token in lowered for token in _SENSITIVE_PATTERNS)


def _redact(value: Any) -> Any:
    if value is None:
        return value
    if isinstance(value, str):
        if _contains_secret(value):
            return "***REDACTED***"
        return value
    if isinstance(value, dict):
        return {key: _redact(value[key]) for key in value}
    if isinstance(value, (list, tuple, set)):
        container_type = type(value)
        return container_type(_redact(item) for item in value)
    return value


class _RedactionFilter(logging.Filter):
    """Filter that redacts sensitive information from log records."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        for key in list(record.__dict__.keys()):
            if key in {"args", "msg", "message"}:
                continue
            if any(token in key.lower() for token in _SENSITIVE_PATTERNS):
                record.__dict__[key] = "***REDACTED***"
            else:
                record.__dict__[key] = _redact(record.__dict__[key])

        if isinstance(record.args, dict):
            record.args = {key: _redact(value) for key, value in record.args.items()}
        elif isinstance(record.args, Iterable) and not isinstance(record.args, str):
            record.args = tuple(_redact(value) for value in record.args)

        if isinstance(record.msg, str) and _contains_secret(record.msg):
            record.msg = "***REDACTED***"
        return True


class _JsonFormatter(logging.Formatter):
    """Formatter that outputs structured JSON payloads."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", _CORRELATION_ID),
        }
        for key, value in record.__dict__.items():
            if key in {
                "args",
                "msg",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
            }:
                continue
            payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class _StructuredFormatter(logging.Formatter):
    """Plain-text structured formatter."""

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)sZ %(levelname)s %(name)s [corr=%(correlation_id)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: D401, N802
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return dt.strftime(self.datefmt or "%Y-%m-%dT%H:%M:%S")


def configure_logging(level_override: str | None = None) -> None:
    """Configure the global logging system if it has not been configured."""

    global _CONFIGURED

    with _CONFIG_LOCK:
        handler: logging.Handler
        root = logging.getLogger()
        first_configuration = not _CONFIGURED
        if first_configuration:
            handler = logging.StreamHandler(stream=sys.stdout)
            use_json = os.getenv("RC_LOG_JSON", "false").lower() == "true"
            handler.addFilter(_CorrelationIdFilter())
            handler.addFilter(_RedactionFilter())
            handler.setFormatter(_JsonFormatter() if use_json else _StructuredFormatter())
            root.handlers = [handler]
            root.propagate = False
            _CONFIGURED = True

        level: int | None = None
        if level_override:
            try:
                level = getattr(logging, level_override.upper())
            except AttributeError:
                level = logging.INFO
        elif first_configuration:
            env_level = os.getenv("RC_LOG_LEVEL", "INFO").upper()
            level = getattr(logging, env_level, logging.INFO)

        if level is not None:
            root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger instance."""

    configure_logging()
    return logging.getLogger(name)


def parse_retry_after(value: str) -> float | None:
    """Parse a Retry-After header value into seconds."""

    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        try:
            retry_dt = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if retry_dt is None:
            return None
        if retry_dt.tzinfo is None:
            retry_dt = retry_dt.replace(tzinfo=timezone.utc)
        delta = (retry_dt - datetime.now(timezone.utc)).total_seconds()
        return max(delta, 0)


__all__ = ["get_logger", "configure_logging", "get_correlation_id", "parse_retry_after"]

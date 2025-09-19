"""Shim handler exposing the canonical audit Lambda entrypoint."""
from __future__ import annotations

from typing import Any, Dict

from .lambda_handler import lambda_handler as _delegate


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Proxy to the historical ``lambda_handler`` function."""
    return _delegate(event, context)

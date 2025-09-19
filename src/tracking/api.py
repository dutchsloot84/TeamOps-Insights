"""Public API for comparing audit run artifacts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .diff import diff_runs


def _load_reference(ref: Any) -> Mapping[str, Any]:
    if isinstance(ref, Mapping):
        return ref
    if isinstance(ref, (str, Path)):
        path = Path(ref)
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, Mapping):  # pragma: no cover - defensive
            raise TypeError("Loaded JSON is not a mapping")
        return data
    raise TypeError("Unsupported reference type. Expected mapping or path-like object.")


def compare(old_ref: Any, new_ref: Any) -> dict[str, Any]:
    """Compare two references pointing to audit runs."""

    old_payload = _load_reference(old_ref)
    new_payload = _load_reference(new_ref)
    return diff_runs(old_payload, new_payload)

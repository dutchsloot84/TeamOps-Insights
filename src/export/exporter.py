"""Utilities for exporting audit data to JSON/Excel for compatibility with tooling."""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Dict, Mapping as TypingMapping

from exporters.excel_exporter import ExcelExporter
from exporters.json_exporter import JSONExporter

_SUPPORTED_FORMATS = {"json", "excel"}


def build_export_payload(
    data: Mapping[str, Any] | None = None,
    *,
    matched: Iterable[Dict[str, Any]] | None = None,
    missing: Iterable[Dict[str, Any]] | None = None,
    orphans: Iterable[Dict[str, Any]] | None = None,
    summary: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Create a normalized payload for downstream exporters.

    The function accepts either a consolidated mapping ``data`` containing the
    canonical keys (``summary``, ``stories_with_no_commits``,
    ``orphan_commits`` and ``commit_story_mapping``) or the individual pieces
    which are then merged into the expected structure.
    """

    if data is not None and any(item is not None for item in (matched, missing, orphans, summary)):
        raise ValueError("Provide either `data` or the individual components, not both")

    if data is None:
        payload_source: Mapping[str, Any] = {
            "summary": dict(summary or {}),
            "stories_with_no_commits": list(missing or []),
            "orphan_commits": list(orphans or []),
            "commit_story_mapping": list(matched or []),
        }
    else:
        payload_source = data

    return {
        "summary": dict(payload_source.get("summary", {})),
        "stories_with_no_commits": list(payload_source.get("stories_with_no_commits", []) or []),
        "orphan_commits": list(payload_source.get("orphan_commits", []) or []),
        "commit_story_mapping": list(payload_source.get("commit_story_mapping", []) or []),
    }


def _normalise_formats(formats: Iterable[str] | None) -> set[str]:
    if formats is None:
        return set(_SUPPORTED_FORMATS)
    requested = {fmt.strip().lower() for fmt in formats if fmt}
    invalid = requested - _SUPPORTED_FORMATS
    if invalid:
        raise ValueError(f"Unsupported export formats requested: {sorted(invalid)}")
    return requested or set(_SUPPORTED_FORMATS)


def export_all(
    data: Mapping[str, Any] | Iterable[Dict[str, Any]],
    missing: Iterable[Dict[str, Any]] | None = None,
    orphans: Iterable[Dict[str, Any]] | None = None,
    summary: Mapping[str, Any] | None = None,
    *,
    out_dir: str | Path | None,
    formats: Iterable[str] | None = None,
    filenames: TypingMapping[str, str | Path] | None = None,
) -> Dict[str, Path]:
    """Export the combined payload to JSON and Excel formats.

    ``data`` may either be the pre-assembled payload mapping or the list of
    commit mappings for backwards compatibility with legacy call sites.
    """

    if isinstance(data, Mapping):
        payload = build_export_payload(data=data)
    else:
        payload = build_export_payload(
            matched=data,
            missing=missing,
            orphans=orphans,
            summary=summary,
        )

    requested_formats = _normalise_formats(formats)

    base_dir = Path(out_dir) if out_dir is not None else None
    resolved: Dict[str, Path] = {}

    def _resolve(name: str, default: str) -> Path:
        if filenames and name in filenames:
            path = Path(filenames[name]).resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            return path
        if base_dir is None:
            raise ValueError(
                "`out_dir` must be provided when explicit filenames are not supplied"
            )
        base_dir.mkdir(parents=True, exist_ok=True)
        return (base_dir / default).resolve()

    if "json" in requested_formats:
        resolved["json"] = _resolve("json", "audit_results.json")
    if "excel" in requested_formats:
        resolved["excel"] = _resolve("excel", "audit_results.xlsx")
    resolved["summary"] = _resolve("summary", "summary.json")

    outputs: Dict[str, Path] = {}

    if "json" in requested_formats:
        json_path = resolved["json"]
        json_exporter = JSONExporter(json_path.parent)
        outputs["json"] = json_exporter.export(payload, json_path.name)
    if "excel" in requested_formats:
        excel_path = resolved["excel"]
        excel_exporter = ExcelExporter(excel_path.parent)
        outputs["excel"] = excel_exporter.export(payload, excel_path.name)

    summary_path = resolved["summary"]
    summary_path.write_text(json.dumps(payload["summary"], indent=2), encoding="utf-8")
    outputs["summary"] = summary_path

    return outputs


__all__ = ["build_export_payload", "export_all"]

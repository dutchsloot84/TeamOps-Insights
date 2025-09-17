"""Utilities for exporting audit data to JSON/Excel for compatibility with tooling."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable

from exporters.excel_exporter import ExcelExporter
from exporters.json_exporter import JSONExporter


def export_all(
    matched: Iterable[Dict[str, Any]],
    missing: Iterable[Dict[str, Any]],
    orphans: Iterable[Dict[str, Any]],
    summary: Dict[str, Any],
    *,
    out_dir: str | Path,
) -> Dict[str, Path]:
    """Export the combined payload to JSON and Excel formats."""
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    payload: Dict[str, Any] = {
        "summary": dict(summary),
        "stories_with_no_commits": list(missing),
        "orphan_commits": list(orphans),
        "commit_story_mapping": list(matched),
    }

    json_exporter = JSONExporter(output_dir)
    excel_exporter = ExcelExporter(output_dir)

    json_path = json_exporter.export(payload, "audit_results.json")
    excel_path = excel_exporter.export(payload, "audit_results.xlsx")

    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(payload["summary"], indent=2), encoding="utf-8")

    return {
        "json": json_path,
        "excel": excel_path,
        "summary": summary_path,
    }


__all__ = ["export_all"]

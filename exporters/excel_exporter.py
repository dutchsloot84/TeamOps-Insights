"""Excel export utilities for audit results."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


class ExcelExporter:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, data: Dict[str, Any], filename: str = "audit_results.xlsx") -> Path:
        output_path = self.output_dir / filename
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            self._write_summary_sheet(data.get("summary", {}), writer)
            self._write_table_sheet(
                data.get("stories_with_no_commits", []),
                "Stories Without Commits",
                writer,
            )
            self._write_table_sheet(data.get("orphan_commits", []), "Orphan Commits", writer)
            self._write_mapping_sheet(data.get("commit_story_mapping", []), writer)
        return output_path

    def _write_summary_sheet(self, summary: Dict[str, Any], writer: pd.ExcelWriter) -> None:
        df = pd.DataFrame([summary]) if summary else pd.DataFrame()
        df.to_excel(writer, sheet_name="Audit Summary", index=False)

    def _write_table_sheet(
        self,
        items: List[Dict[str, Any]],
        sheet_name: str,
        writer: pd.ExcelWriter,
    ) -> None:
        df = pd.json_normalize(items) if items else pd.DataFrame()
        df.to_excel(writer, sheet_name=sheet_name[:31], index=False)

    def _write_mapping_sheet(self, mappings: List[Dict[str, Any]], writer: pd.ExcelWriter) -> None:
        rows: List[Dict[str, Any]] = []
        for mapping in mappings:
            commits = mapping.get("commits", [])
            if not commits:
                rows.append({"story_key": mapping.get("story_key"), "commit_hash": None, "commit_message": None})
                continue
            for commit in commits:
                rows.append(
                    {
                        "story_key": mapping.get("story_key"),
                        "story_summary": mapping.get("story_summary"),
                        "commit_hash": commit.get("hash"),
                        "commit_message": commit.get("message"),
                        "commit_author": commit.get("author"),
                        "commit_date": commit.get("date"),
                        "repository": commit.get("repository"),
                        "branch": commit.get("branch"),
                    }
                )
        df = pd.DataFrame(rows)
        df.to_excel(writer, sheet_name="Commit Mapping", index=False)

"""Rebuild export artifacts from cached payloads without external API calls."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple

from src.export.exporter import export_all
from src.matcher.engine import match


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Expected payload at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def recover_from_payloads(raw_dir: str | Path, out_dir: str | Path) -> Tuple[str, str]:
    raw_path = Path(raw_dir)
    output_path = Path(out_dir)
    issues_payload = _load_json(raw_path / "jira_issues.json")
    commits_payload = _load_json(raw_path / "bitbucket_commits.json")

    issues = issues_payload.get("issues", issues_payload)
    commits = commits_payload.get("commits", commits_payload)

    matched, missing, orphans, summary = match(issues, commits)
    exports = export_all(matched, missing, orphans, summary, out_dir=output_path)

    return str(exports["json"]), str(exports["excel"])


def main(raw_dir: str = "data/raw", out_dir: str = "artifacts") -> None:
    json_path, excel_path = recover_from_payloads(raw_dir, out_dir)
    print(f"Rebuilt artifacts: {json_path}, {excel_path}")


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()

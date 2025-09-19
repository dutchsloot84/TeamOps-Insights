from pathlib import Path

from src.export.exporter import export_all


def test_export_creates_files(tmp_path: Path) -> None:
    payload = {
        "summary": {"total_issues": 2},
        "stories_with_no_commits": [{"key": "MOB-2"}],
        "orphan_commits": [{"message": "refactor"}],
        "commit_story_mapping": [{"issue_key": "MOB-1", "commit": {"hash": "abc"}}],
    }

    outputs = export_all(payload, out_dir=tmp_path)

    assert (tmp_path / "audit_results.json").exists()
    assert (tmp_path / "audit_results.xlsx").exists()
    assert (tmp_path / "summary.json").exists()
    assert outputs["json"].exists()
    assert outputs["excel"].exists()

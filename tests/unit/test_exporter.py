from pathlib import Path

from src.export.exporter import export_all


def test_export_creates_files(tmp_path: Path) -> None:
    matched = [
        {"issue_key": "MOB-1", "commit": {"hash": "abc"}},
    ]
    missing = [{"key": "MOB-2"}]
    orphans = [{"message": "refactor"}]
    summary = {"total_issues": 2}

    outputs = export_all(matched, missing, orphans, summary, out_dir=tmp_path)

    assert (tmp_path / "audit_results.json").exists()
    assert (tmp_path / "audit_results.xlsx").exists()
    assert (tmp_path / "summary.json").exists()
    assert outputs["json"].exists()
    assert outputs["excel"].exists()

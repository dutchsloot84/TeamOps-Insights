from __future__ import annotations

import json
from pathlib import Path

import pytest

from tracking import api as tracking_api
from tracking.diff import diff_runs, render_diff_markdown


@pytest.fixture()
def sample_runs() -> tuple[dict[str, object], dict[str, object]]:
    base = Path(__file__).parents[2] / "fixtures" / "tracking"
    with (base / "old_run.json").open("r", encoding="utf-8") as fh:
        old_data = json.load(fh)
    with (base / "new_run.json").open("r", encoding="utf-8") as fh:
        new_data = json.load(fh)
    return old_data, new_data


def test_diff_runs_detects_changes(sample_runs: tuple[dict[str, object], dict[str, object]]) -> None:
    old_run, new_run = sample_runs
    diff = diff_runs(old_run, new_run)

    assert diff["stories_added"] == ["RC-3"]
    assert diff["stories_removed"] == ["RC-2"]
    assert diff["status_changes"] == [
        {"key": "RC-1", "from": "In Progress", "to": "Done"},
    ]
    assert diff["assignee_changes"] == [
        {"key": "RC-1", "from": "Alice", "to": "Bob"},
    ]
    assert diff["commits_added"] == [
        {"key": "RC-1", "commit_ids": ["c2"]},
        {"key": "RC-3", "commit_ids": ["c3"]},
    ]
    assert diff["commits_removed"] == []
    assert diff["new_orphans"] == ["c-orphan-new"]
    assert diff["resolved_orphans"] == ["c-orphan-old"]
    assert diff["coverage_previous"] == 50.0
    assert diff["coverage_current"] == 100.0
    assert diff["coverage_delta"] == 50.0


def test_render_diff_markdown(sample_runs: tuple[dict[str, object], dict[str, object]]) -> None:
    old_run, new_run = sample_runs
    diff = diff_runs(old_run, new_run)

    markdown = render_diff_markdown(diff)
    assert "Stories added: RC-3" in markdown
    assert "Stories removed: RC-2" in markdown
    assert "Coverage changed by +50.00%" in markdown


def test_compare_supports_paths(tmp_path: Path, sample_runs: tuple[dict[str, object], dict[str, object]]) -> None:
    old_run, new_run = sample_runs
    old_path = tmp_path / "old.json"
    new_path = tmp_path / "new.json"
    old_path.write_text(json.dumps(old_run), encoding="utf-8")
    new_path.write_text(json.dumps(new_run), encoding="utf-8")

    diff = tracking_api.compare(old_path, new_path)
    assert diff["stories_added"] == ["RC-3"]

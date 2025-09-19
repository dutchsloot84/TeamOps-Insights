from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ui import transform


def _load_sample_report() -> dict:
    path = Path(__file__).resolve().parents[3] / "reports" / "sample.json"
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def test_compute_kpis_uses_summary_when_available() -> None:
    report = _load_sample_report()
    metrics = transform.compute_kpis(report)

    assert metrics["total_stories"] == 3
    assert metrics["stories_with_commits"] == 2
    assert metrics["stories_without_commits"] == 1
    assert metrics["orphan_commits"] == 1
    assert metrics["coverage_percent"] == 66.67


def test_filters_by_fix_version_and_repository() -> None:
    report = _load_sample_report()
    with_df, without_df = transform.prepare_story_tables(report)

    filters = {"fix_versions": ["MOB-1.1.0"]}
    filtered_with, filtered_without = transform.filter_story_tables(with_df, without_df, filters)

    assert filtered_with["story_key"].tolist() == ["APP-3"]
    assert filtered_without.empty

    filters = {"repositories": ["mobile-app"], "branches": ["release/1.0"]}
    filtered_with, _ = transform.filter_story_tables(with_df, without_df, filters)
    assert filtered_with["story_key"].tolist() == ["APP-3"]


def test_orphan_filters_by_date_range() -> None:
    report = _load_sample_report()
    orphan_df = transform.build_orphan_dataframe(report)
    filters = {
        "repositories": ["shared-lib"],
        "date_range": (
            pd.Timestamp("2024-02-09T00:00:00Z"),
            pd.Timestamp("2024-02-09T23:59:59Z"),
        ),
    }

    filtered = transform.filter_orphan_commits(orphan_df, filters)
    assert filtered["hash"].tolist() == ["xyz999"]


def test_filter_options_surface_unique_values() -> None:
    report = _load_sample_report()
    with_df, without_df = transform.prepare_story_tables(report)
    orphan_df = transform.build_orphan_dataframe(report)

    options = transform.get_filter_options(with_df, without_df, orphan_df)

    assert "MOB-1.0.0" in options["fix_versions"]
    assert "Done" in options["statuses"]
    assert "Alice Smith" in options["assignees"]
    assert "Tracking" in options["components_labels"]
    assert "mobile-app" in options["repositories"]
    assert options["date_range"][0] == pd.Timestamp("2024-02-09T08:00:00Z")

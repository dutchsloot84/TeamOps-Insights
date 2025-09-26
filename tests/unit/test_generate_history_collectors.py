"""Unit tests for Git Historian collectors."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from scripts import generate_history
from scripts.github.projects_v2 import ProjectStatusItem

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_collect_project_section_prefers_projects() -> None:
    data = load_fixture("projects_v2_items.json")

    class FakeProjectsClient:
        def query_issues_with_status(self, owner, repo, project_name, status_field, status_values):
            return [ProjectStatusItem(**item) for item in data["items"]]

    class RejectingRestClient:
        def list_open_issues_with_label(self, label: str):  # pragma: no cover - should not be called
            raise AssertionError("label fallback should not run when projects data is available")

    result = generate_history._collect_project_section(  # type: ignore[attr-defined]
        owner="org",
        repo="repo",
        client=RejectingRestClient(),
        projects_client=FakeProjectsClient(),
        section_config={
            "project_v2": {
                "enabled": True,
                "project_name": "Release Copilot",
                "status_field": "Status",
                "status_values": ["In Progress"],
            }
        },
        fallback_status="In Progress",
    )

    assert result.count == 1
    assert "Status: In Progress" in result.entries[0]
    assert result.metadata["issue_status"] == {314: "In Progress"}
    assert any("Project 'Release Copilot'" in line for line in result.filters)


def test_collect_project_section_label_fallback() -> None:
    class LabelRestClient:
        def list_open_issues_with_label(self, label: str):
            return [
                generate_history.Issue(
                    number=42,
                    title="Backlog prep",
                    url="https://github.com/org/repo/issues/42",
                    closed_at=None,
                    assignees=[],
                    labels=[label],
                    status=None,
                )
            ]

    result = generate_history._collect_project_section(  # type: ignore[attr-defined]
        owner="org",
        repo="repo",
        client=LabelRestClient(),
        projects_client=None,
        section_config={"labels": ["backlog"]},
        fallback_status="Backlog",
    )

    assert result.count == 1
    assert "Status: Backlog" in result.entries[0]
    assert result.metadata["issue_status"] == {42: "Backlog"}
    assert any("labeled" in line.lower() for line in result.filters)


def test_collect_notes_section_aggregates_markers(monkeypatch: pytest.MonkeyPatch) -> None:
    data = load_fixture("notes_comments.json")

    class FakeClient:
        def list_issue_comments(self, since: dt.datetime):
            return data["comments"]

        def list_review_comments(self, since: dt.datetime):
            return data["review_comments"]

    monkeypatch.setattr(generate_history, "_collect_local_notes", lambda root, since: [])
    monkeypatch.setattr(generate_history, "_collect_jira_references", lambda root, since: [])

    since = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
    until = dt.datetime(2024, 1, 7, tzinfo=dt.timezone.utc)

    result = generate_history._collect_notes_section(  # type: ignore[attr-defined]
        client=FakeClient(),
        notes_config={
            "comment_markers": ["Decision:", "Note:", "Action:"],
            "scan_issue_comments": True,
            "scan_pr_comments": True,
            "annotate_group": True,
        },
        status_lookup={
            ("issue", 77): "In Progress",
            ("pull_request", 12): "Completed",
        },
        since=since,
        until=until,
        root=Path("."),
    )

    assert result.count == 3
    assert any(entry.startswith("- **Decision:") for entry in result.entries)
    assert any("In Progress" in entry for entry in result.entries)
    assert any("Completed" in entry for entry in result.entries)
    assert any("@octocat" in entry for entry in result.entries)
    assert result.filters[0].startswith("Markers:")


def test_collect_artifacts_section_combines_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    data = load_fixture("gha_artifacts.json")

    class FakeClient:
        def list_workflow_runs(self, workflow: str):
            return data["workflow_runs"]

        def list_run_artifacts(self, run_id: int):
            for entry in data["artifacts"]:
                if entry["run_id"] == run_id:
                    return entry["items"]
            return []

    monkeypatch.setattr(
        generate_history,
        "_collect_s3_artifacts",
        lambda bucket, prefixes, since, until: [
            "- S3 releasecopilot-artifacts → `reports/report.csv` (0 bytes, updated 2024-01-05)"
        ],
    )

    since = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
    until = dt.datetime(2024, 1, 10, tzinfo=dt.timezone.utc)

    result = generate_history._collect_artifacts_section(  # type: ignore[attr-defined]
        client=FakeClient(),
        artifacts_config={
            "github_actions": {"enabled": True, "workflows": ["ci.yml"]},
            "s3": {
                "enabled": True,
                "bucket": "releasecopilot-artifacts",
                "prefixes": ["reports/"],
            },
        },
        since=since,
        until=until,
    )

    assert result.count == 2
    assert "Workflow" in " \n".join(result.entries)
    assert any("S3" in entry for entry in result.entries)
    assert any("GitHub Actions" in line for line in result.filters)
    assert any("s3://releasecopilot-artifacts" in line for line in result.filters)


def test_collect_completed_combines_sources() -> None:
    pr = generate_history.PullRequest(
        number=7,
        title="Add metrics",
        url="https://github.com/org/repo/pull/7",
        merged_at=dt.datetime(2024, 1, 2, tzinfo=dt.timezone.utc),
        author="octocat",
    )
    issue = generate_history.Issue(
        number=9,
        title="Fix deployment",
        url="https://github.com/org/repo/issues/9",
        closed_at=dt.datetime(2024, 1, 3, tzinfo=dt.timezone.utc),
        assignees=["octocat"],
        labels=["bug"],
    )

    result = generate_history._collect_completed([pr], [issue])  # type: ignore[attr-defined]

    assert result.count == 2
    assert "PR [#7]" in result.entries[0]
    assert "Issue [#9]" in "\n".join(result.entries)
    assert result.metadata["issue_numbers"] == {9}
    assert result.metadata["pr_numbers"] == {7}

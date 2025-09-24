"""Unit tests for deterministic diffing of audit runs."""
from __future__ import annotations

from tracking.diff import diff_runs


def test_diff_runs_returns_sorted_changes() -> None:
    """``diff_runs`` should produce predictable ordering for all sections."""

    old_run = {
        "stories": [
            {
                "key": "STORY-1",
                "status": "In Progress",
                "assignee": "Alice",
                "commitIds": ["a1"],
            },
            {
                "key": "STORY-2",
                "status": "Review",
                "assignee": "Bob",
                "commitIds": ["legacy"],
            },
        ],
        "commits": [
            {"id": "a1", "linkedStoryKeys": ["STORY-1"]},
            {"id": "legacy", "linkedStoryKeys": ["STORY-2"]},
            {"id": "orphan-old", "linkedStoryKeys": []},
        ],
    }

    new_run = {
        "stories": [
            {
                "key": "STORY-1",
                "status": "Done",
                "assignee": "Charlie",
                "commitIds": ["a1", "b2"],
            },
            {
                "key": "STORY-3",
                "status": "In Progress",
                "assignee": "Dana",
                "commitIds": ["c3"],
            },
        ],
        "commits": [
            {"id": "a1", "linkedStoryKeys": ["STORY-1"]},
            {"id": "b2", "linkedStoryKeys": ["STORY-1"]},
            {"id": "c3", "linkedStoryKeys": ["STORY-3"]},
            {"id": "orphan-new", "linkedStoryKeys": []},
        ],
    }

    diff = diff_runs(old_run, new_run)

    assert diff["stories_added"] == ["STORY-3"]
    assert diff["stories_removed"] == ["STORY-2"]
    assert diff["status_changes"] == [
        {"key": "STORY-1", "from": "In Progress", "to": "Done"}
    ]
    assert diff["assignee_changes"] == [
        {"key": "STORY-1", "from": "Alice", "to": "Charlie"}
    ]
    assert diff["commits_added"] == [
        {"key": "STORY-1", "commit_ids": ["b2"]},
        {"key": "STORY-3", "commit_ids": ["c3"]},
    ]
    assert diff["commits_removed"] == [
        {"key": "STORY-2", "commit_ids": ["legacy"]}
    ]
    assert diff["new_orphans"] == ["orphan-new"]
    assert diff["resolved_orphans"] == ["orphan-old"]
    assert diff["coverage_previous"] == 100.0
    assert diff["coverage_current"] == 100.0
    assert diff["coverage_delta"] == 0.0

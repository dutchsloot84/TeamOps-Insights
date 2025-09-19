"""Diff utilities for comparing audit run JSON artifacts."""
from __future__ import annotations

from typing import Dict, List, Mapping, Sequence


def _is_sequence(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _story_index(run: Mapping[str, object]) -> Dict[str, Mapping[str, object]]:
    stories = run.get("stories")
    if not _is_sequence(stories):
        return {}
    index: Dict[str, Mapping[str, object]] = {}
    for story in stories:  # type: ignore[assignment]
        if isinstance(story, Mapping):
            key = story.get("key")
            if isinstance(key, str) and key:
                index[key] = story
    return index


def _story_commit_ids(story: Mapping[str, object]) -> List[str]:
    commit_ids = story.get("commitIds")
    if not _is_sequence(commit_ids):
        return []
    values: List[str] = []
    for commit_id in commit_ids:  # type: ignore[assignment]
        if isinstance(commit_id, str):
            values.append(commit_id)
    return values


def _orphans(run: Mapping[str, object]) -> List[str]:
    commits = run.get("commits")
    if not _is_sequence(commits):
        return []
    orphan_ids: List[str] = []
    for commit in commits:  # type: ignore[assignment]
        if not isinstance(commit, Mapping):
            continue
        linked = commit.get("linkedStoryKeys")
        if _is_sequence(linked) and len(linked) > 0:
            continue
        if isinstance(linked, (str, bytes, bytearray)) and linked:
            continue
        commit_id = commit.get("id")
        if isinstance(commit_id, str):
            orphan_ids.append(commit_id)
    return sorted(orphan_ids)


def _coverage_percent(run: Mapping[str, object]) -> float:
    stories = list(_story_index(run).values())
    total = len(stories)
    if total == 0:
        return 0.0
    with_commits = sum(1 for story in stories if _story_commit_ids(story))
    return round((with_commits / total) * 100, 2)


def _diff_commit_lists(
    old: Mapping[str, object], new: Mapping[str, object]
) -> tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    added: List[Dict[str, object]] = []
    removed: List[Dict[str, object]] = []

    old_index = _story_index(old)
    new_index = _story_index(new)
    shared_keys = sorted(set(old_index) & set(new_index))
    new_only_keys = sorted(set(new_index) - set(old_index))
    removed_keys = sorted(set(old_index) - set(new_index))

    for key in shared_keys:
        old_commits = set(_story_commit_ids(old_index[key]))
        new_commits = set(_story_commit_ids(new_index[key]))

        added_ids = sorted(new_commits - old_commits)
        removed_ids = sorted(old_commits - new_commits)

        if added_ids:
            added.append({"key": key, "commit_ids": added_ids})
        if removed_ids:
            removed.append({"key": key, "commit_ids": removed_ids})

    for key in new_only_keys:
        commit_ids = sorted(set(_story_commit_ids(new_index[key])))
        if commit_ids:
            added.append({"key": key, "commit_ids": commit_ids})

    for key in removed_keys:
        commit_ids = sorted(set(_story_commit_ids(old_index[key])))
        if commit_ids:
            removed.append({"key": key, "commit_ids": commit_ids})

    added.sort(key=lambda item: item.get("key", ""))
    removed.sort(key=lambda item: item.get("key", ""))

    return added, removed


def diff_runs(old: Mapping[str, object], new: Mapping[str, object]) -> Dict[str, object]:
    """Generate a deterministic diff structure between two audit runs."""

    old_index = _story_index(old)
    new_index = _story_index(new)

    old_keys = set(old_index)
    new_keys = set(new_index)

    stories_added = sorted(new_keys - old_keys)
    stories_removed = sorted(old_keys - new_keys)

    status_changes: List[Dict[str, object]] = []
    assignee_changes: List[Dict[str, object]] = []

    for key in sorted(old_keys & new_keys):
        old_story = old_index[key]
        new_story = new_index[key]

        old_status = old_story.get("status") if isinstance(old_story, Mapping) else None
        new_status = new_story.get("status") if isinstance(new_story, Mapping) else None
        if old_status != new_status:
            status_changes.append({"key": key, "from": old_status, "to": new_status})

        old_assignee = (
            old_story.get("assignee") if isinstance(old_story, Mapping) else None
        )
        new_assignee = (
            new_story.get("assignee") if isinstance(new_story, Mapping) else None
        )
        if old_assignee != new_assignee:
            assignee_changes.append({"key": key, "from": old_assignee, "to": new_assignee})

    commits_added, commits_removed = _diff_commit_lists(old, new)

    old_orphans = _orphans(old)
    new_orphans = _orphans(new)

    new_orphan_ids = sorted(set(new_orphans) - set(old_orphans))
    resolved_orphan_ids = sorted(set(old_orphans) - set(new_orphans))

    previous_coverage = _coverage_percent(old)
    current_coverage = _coverage_percent(new)

    return {
        "stories_added": stories_added,
        "stories_removed": stories_removed,
        "status_changes": status_changes,
        "assignee_changes": assignee_changes,
        "commits_added": commits_added,
        "commits_removed": commits_removed,
        "new_orphans": new_orphan_ids,
        "resolved_orphans": resolved_orphan_ids,
        "coverage_previous": previous_coverage,
        "coverage_current": current_coverage,
        "coverage_delta": round(current_coverage - previous_coverage, 2),
    }


def render_diff_markdown(diff: Mapping[str, object]) -> str:
    """Render a markdown bullet summary for a diff."""

    lines: List[str] = []

    stories_added = diff.get("stories_added")
    if isinstance(stories_added, Sequence) and stories_added:
        items = ", ".join(str(item) for item in stories_added)
        lines.append(f"- Stories added: {items}")

    stories_removed = diff.get("stories_removed")
    if isinstance(stories_removed, Sequence) and stories_removed:
        items = ", ".join(str(item) for item in stories_removed)
        lines.append(f"- Stories removed: {items}")

    status_changes = diff.get("status_changes")
    if isinstance(status_changes, Sequence) and status_changes:
        changes = ", ".join(
            f"{item.get('key')}: {item.get('from')} → {item.get('to')}"
            for item in status_changes
            if isinstance(item, Mapping)
        )
        if changes:
            lines.append(f"- Status changes: {changes}")

    assignee_changes = diff.get("assignee_changes")
    if isinstance(assignee_changes, Sequence) and assignee_changes:
        changes = ", ".join(
            f"{item.get('key')}: {item.get('from')} → {item.get('to')}"
            for item in assignee_changes
            if isinstance(item, Mapping)
        )
        if changes:
            lines.append(f"- Assignee changes: {changes}")

    new_orphans = diff.get("new_orphans")
    if isinstance(new_orphans, Sequence) and new_orphans:
        items = ", ".join(str(item) for item in new_orphans)
        lines.append(f"- New orphan commits: {items}")

    resolved_orphans = diff.get("resolved_orphans")
    if isinstance(resolved_orphans, Sequence) and resolved_orphans:
        items = ", ".join(str(item) for item in resolved_orphans)
        lines.append(f"- Resolved orphan commits: {items}")

    coverage_delta = diff.get("coverage_delta")
    if isinstance(coverage_delta, (int, float)) and coverage_delta:
        current = diff.get("coverage_current")
        previous = diff.get("coverage_previous")
        if isinstance(current, (int, float)) and isinstance(previous, (int, float)):
            lines.append(
                f"- Coverage changed by {coverage_delta:+.2f}% (from {previous:.2f}% to {current:.2f}%)"
            )
        else:
            lines.append(f"- Coverage changed by {coverage_delta:+.2f}%")

    if not lines:
        return "No differences detected."
    return "\n".join(lines)

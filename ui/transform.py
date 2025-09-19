"""Transform helpers for the Streamlit dashboard."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence, Tuple

import pandas as pd

StoryFilters = Dict[str, Any]


def compute_kpis(report: Dict[str, Any]) -> Dict[str, Any]:
    """Compute KPI metrics for the dashboard."""

    summary = report.get("summary", {})
    total_stories = summary.get("total_stories")
    stories_with_commits = summary.get("stories_with_commits")
    stories_without_commits = summary.get("stories_without_commits")

    if total_stories is None:
        with_commits = len(report.get("commit_story_mapping", []))
        without_commits = len(report.get("stories_with_no_commits", []))
        total_stories = with_commits + without_commits
        stories_with_commits = stories_with_commits or with_commits
        stories_without_commits = stories_without_commits or without_commits

    orphan_commits = summary.get("orphan_commits")
    if orphan_commits is None:
        orphan_commits = len(report.get("orphan_commits", []))

    coverage = 0.0
    if total_stories:
        coverage = (stories_with_commits or 0) / total_stories * 100

    return {
        "total_stories": total_stories,
        "stories_with_commits": stories_with_commits or 0,
        "stories_without_commits": stories_without_commits or 0,
        "orphan_commits": orphan_commits,
        "coverage_percent": round(coverage, 2),
    }


def prepare_story_tables(report: Dict[str, Any]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Return dataframes for stories with and without commits."""

    with_rows: List[Dict[str, Any]] = []
    for entry in report.get("commit_story_mapping", []):
        commits = entry.get("commits", [])
        dates = [pd.to_datetime(commit.get("date")) for commit in commits if commit.get("date")]
        with_rows.append(
            {
                "story_key": entry.get("story_key"),
                "summary": _first_of(
                    entry.get("story_summary"),
                    entry.get("summary"),
                    entry.get("fields", {}).get("summary"),
                ),
                "status": _extract_status(entry),
                "assignee": _extract_assignee(entry),
                "fix_versions": _extract_names(entry, "fix_versions"),
                "components": _extract_names(entry, "components"),
                "labels": _ensure_list(entry.get("labels")),
                "all_labels": _collect_labels(entry),
                "repositories": sorted(
                    {
                        commit.get("repository")
                        for commit in commits
                        if commit.get("repository")
                    }
                ),
                "branches": sorted(
                    {
                        commit.get("branch")
                        for commit in commits
                        if commit.get("branch")
                    }
                ),
                "latest_commit_date": max(dates) if dates else pd.NaT,
                "commit_count": len(commits),
                "has_commits": True,
            }
        )

    without_rows: List[Dict[str, Any]] = []
    for entry in report.get("stories_with_no_commits", []):
        fields = entry.get("fields", {})
        without_rows.append(
            {
                "story_key": entry.get("key"),
                "summary": fields.get("summary"),
                "status": _extract_status(entry),
                "assignee": _extract_assignee(entry),
                "fix_versions": _extract_names(entry, "fixVersions"),
                "components": _extract_names(entry, "components"),
                "labels": _ensure_list(fields.get("labels")),
                "all_labels": _collect_labels(entry),
                "repositories": [],
                "branches": [],
                "latest_commit_date": pd.NaT,
                "commit_count": 0,
                "has_commits": False,
            }
        )

    columns = [
        "story_key",
        "summary",
        "status",
        "assignee",
        "fix_versions",
        "components",
        "labels",
        "all_labels",
        "repositories",
        "branches",
        "latest_commit_date",
        "commit_count",
        "has_commits",
    ]
    with_df = pd.DataFrame(with_rows, columns=columns)
    without_df = pd.DataFrame(without_rows, columns=columns)
    return with_df, without_df


def build_orphan_dataframe(report: Dict[str, Any]) -> pd.DataFrame:
    """Return dataframe for orphan commits."""

    rows = []
    for commit in report.get("orphan_commits", []):
        rows.append(
            {
                "hash": commit.get("hash"),
                "message": commit.get("message"),
                "author": commit.get("author"),
                "date": pd.to_datetime(commit.get("date")) if commit.get("date") else pd.NaT,
                "repository": commit.get("repository"),
                "branch": commit.get("branch"),
            }
        )
    return pd.DataFrame(rows, columns=["hash", "message", "author", "date", "repository", "branch"])


def filter_story_tables(
    stories_with_commits: pd.DataFrame,
    stories_without_commits: pd.DataFrame,
    filters: StoryFilters,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Apply sidebar filters to story tables."""

    filtered_with = _apply_story_filters(stories_with_commits, filters)
    filtered_without = _apply_story_filters(stories_without_commits, filters)
    return filtered_with, filtered_without


def filter_orphan_commits(orphan_df: pd.DataFrame, filters: StoryFilters) -> pd.DataFrame:
    """Apply filters to the orphan commits table."""

    if orphan_df.empty:
        return orphan_df

    df = orphan_df.copy()
    repositories = filters.get("repositories")
    if repositories:
        df = df[df["repository"].isin(repositories)]

    branches = filters.get("branches")
    if branches:
        df = df[df["branch"].isin(branches)]

    date_range = filters.get("date_range")
    if date_range and not df.empty:
        start, end = date_range
        if start:
            df = df[df["date"].notna() & (df["date"] >= start)]
        if end:
            df = df[df["date"] <= end]

    return df


def get_filter_options(
    stories_with_commits: pd.DataFrame,
    stories_without_commits: pd.DataFrame,
    orphan_df: pd.DataFrame,
) -> Dict[str, Sequence[Any]]:
    """Collect filter options from the loaded data."""

    combined = pd.concat([stories_with_commits, stories_without_commits], ignore_index=True)

    fix_versions = sorted(
        {
            item
            for sublist in combined.get("fix_versions", pd.Series(dtype="object"))
            if isinstance(sublist, list)
            for item in sublist
        }
    )
    statuses = sorted({value for value in combined.get("status", []) if value})
    assignees = sorted({value for value in combined.get("assignee", []) if value})
    labels = sorted(
        {
            label
            for sublist in combined.get("all_labels", pd.Series(dtype="object"))
            if isinstance(sublist, list)
            for label in sublist
        }
    )
    repositories = sorted(
        {
            repo
            for sublist in combined.get("repositories", pd.Series(dtype="object"))
            if isinstance(sublist, list)
            for repo in sublist
        }
        | {
            repo
            for repo in orphan_df.get("repository", [])
            if repo
        }
    )
    branches = sorted(
        {
            branch
            for sublist in combined.get("branches", pd.Series(dtype="object"))
            if isinstance(sublist, list)
            for branch in sublist
        }
        | {
            branch
            for branch in orphan_df.get("branch", [])
            if branch
        }
    )

    date_min = pd.NaT
    date_max = pd.NaT
    if not stories_with_commits.empty:
        commit_dates = stories_with_commits["latest_commit_date"].dropna()
        if not commit_dates.empty:
            date_min = commit_dates.min()
            date_max = commit_dates.max()
    if not orphan_df.empty:
        orphan_dates = orphan_df["date"].dropna()
        if not orphan_dates.empty:
            date_min = _min_ignore_na(date_min, orphan_dates.min())
            date_max = _max_ignore_na(date_max, orphan_dates.max())

    return {
        "fix_versions": fix_versions,
        "statuses": statuses,
        "assignees": assignees,
        "components_labels": labels,
        "repositories": repositories,
        "branches": branches,
        "date_range": (date_min, date_max) if date_min is not pd.NaT and date_max is not pd.NaT else None,
    }


def _apply_story_filters(df: pd.DataFrame, filters: StoryFilters) -> pd.DataFrame:
    if df.empty:
        return df

    result = df.copy()

    fix_versions = filters.get("fix_versions")
    if fix_versions:
        result = result[result["fix_versions"].apply(lambda items: _contains_any(items, fix_versions))]

    statuses = filters.get("statuses")
    if statuses:
        result = result[result["status"].isin(statuses)]

    assignees = filters.get("assignees")
    if assignees:
        result = result[result["assignee"].isin(assignees)]

    labels = filters.get("components_labels")
    if labels:
        result = result[result["all_labels"].apply(lambda items: _contains_any(items, labels))]

    repositories = filters.get("repositories")
    if repositories:
        result = result[result["repositories"].apply(lambda items: _contains_any(items, repositories))]

    branches = filters.get("branches")
    if branches:
        result = result[result["branches"].apply(lambda items: _contains_any(items, branches))]

    date_range = filters.get("date_range")
    if date_range:
        start, end = date_range
        if start is not None:
            result = result[result["latest_commit_date"].notna() & (result["latest_commit_date"] >= start)]
        if end is not None:
            result = result[result["latest_commit_date"] <= end]

    return result


def _extract_status(entry: Dict[str, Any]) -> Any:
    if "story_status" in entry:
        return entry.get("story_status")
    fields = entry.get("fields") or {}
    status = fields.get("status")
    if isinstance(status, dict):
        return status.get("name")
    return entry.get("status")


def _extract_assignee(entry: Dict[str, Any]) -> Any:
    if "story_assignee" in entry:
        return entry.get("story_assignee")
    fields = entry.get("fields") or {}
    assignee = fields.get("assignee")
    if isinstance(assignee, dict):
        return assignee.get("displayName") or assignee.get("name")
    return entry.get("assignee")


def _extract_names(entry: Dict[str, Any], key: str) -> List[str]:
    values = entry.get(key)
    if not values and isinstance(entry.get("fields"), dict):
        values = entry["fields"].get(key)
    return _ensure_list(values)


def _collect_labels(entry: Dict[str, Any]) -> List[str]:
    labels: List[str] = []
    for key in ("components", "labels", "fix_versions", "fixVersions"):
        labels.extend(_ensure_list(entry.get(key)))
        fields = entry.get("fields") or {}
        if isinstance(fields, dict) and key in fields:
            labels.extend(_ensure_list(fields.get(key)))
    # deduplicate while preserving order
    seen = set()
    unique = []
    for item in labels:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _ensure_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        result = []
        for item in value:
            if isinstance(item, dict):
                name = item.get("name")
                if name:
                    result.append(str(name))
            elif item:
                result.append(str(item))
        return result
    if isinstance(value, dict):
        name = value.get("name")
        return [str(name)] if name else []
    return [str(value)]


def _contains_any(items: Iterable[Any], candidates: Sequence[Any]) -> bool:
    if isinstance(items, str):
        iterable: Iterable[Any] = [items]
    elif isinstance(items, Iterable):
        iterable = items
    else:
        return False
    items_set = {str(item) for item in iterable if item is not None}
    candidates_set = {str(candidate) for candidate in candidates}
    return bool(items_set & candidates_set)


def _first_of(*values: Any) -> Any:
    for value in values:
        if value:
            return value
    return None


def _min_ignore_na(current: pd.Timestamp, candidate: pd.Timestamp) -> pd.Timestamp:
    if current is pd.NaT:
        return candidate
    return min(current, candidate)


def _max_ignore_na(current: pd.Timestamp, candidate: pd.Timestamp) -> pd.Timestamp:
    if current is pd.NaT:
        return candidate
    return max(current, candidate)

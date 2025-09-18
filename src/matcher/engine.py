"""Adapters that expose audit matching helpers under the ``src.matcher`` namespace."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence, Tuple

from processors.audit_processor import AuditProcessor

Matched = List[Dict[str, Any]]
Missing = List[Dict[str, Any]]
Orphans = List[Dict[str, Any]]
Summary = Dict[str, Any]


def match(
    issues: Sequence[Dict[str, Any]] | Iterable[Dict[str, Any]],
    commits: Sequence[Dict[str, Any]] | Iterable[Dict[str, Any]],
) -> Tuple[Matched, Missing, Orphans, Summary]:
    """Run the audit processor and normalise the results for tests and tooling."""
    processor = AuditProcessor(issues=issues, commits=commits)
    result = processor.process()

    matched: Matched = []
    for mapping in result.commit_story_mapping:
        story_key = mapping.get("story_key")
        for commit in mapping.get("commits", []):
            matched.append({
                "issue_key": story_key,
                "commit": commit,
            })

    summary: Summary = dict(result.summary)
    summary.setdefault("total_issues", summary.get("total_stories", len(issues)))

    return matched, list(result.stories_with_no_commits), list(result.orphan_commits), summary


__all__ = ["match"]

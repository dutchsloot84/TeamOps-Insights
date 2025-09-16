"""Processing utilities that map Jira issues to Bitbucket commits."""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

logger = logging.getLogger(__name__)

STORY_KEY_RE = re.compile(r"[A-Z][A-Z0-9]+-\d+")


@dataclass
class AuditResult:
    summary: Dict[str, Any]
    stories_with_no_commits: List[Dict[str, Any]]
    orphan_commits: List[Dict[str, Any]]
    commit_story_mapping: List[Dict[str, Any]]


class AuditProcessor:
    """Links commits with their corresponding Jira issues."""

    def __init__(self, issues: Iterable[Dict[str, Any]], commits: Iterable[Dict[str, Any]]) -> None:
        self.issues = list(issues)
        self.commits = list(commits)

    def process(self) -> AuditResult:
        issues_by_key = {issue.get("key"): issue for issue in self.issues}
        mapping: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        orphan_commits: List[Dict[str, Any]] = []

        for commit in self.commits:
            message = commit.get("message") or commit.get("summary") or ""
            keys = set(STORY_KEY_RE.findall(message))
            if not keys:
                orphan_commits.append(commit)
                continue
            for key in keys:
                mapping[key].append(commit)

        stories_with_no_commits: List[Dict[str, Any]] = []
        for key, issue in issues_by_key.items():
            if not mapping.get(key):
                stories_with_no_commits.append(issue)

        commit_story_mapping: List[Dict[str, Any]] = []
        for key, commits in mapping.items():
            issue = issues_by_key.get(key, {})
            commit_story_mapping.append(
                {
                    "story_key": key,
                    "story_summary": issue.get("fields", {}).get("summary") if issue else None,
                    "commit_count": len(commits),
                    "commits": [self._simplify_commit(commit) for commit in commits],
                }
            )

        summary = {
            "total_stories": len(self.issues),
            "total_commits": len(self.commits),
            "stories_with_commits": len(commit_story_mapping),
            "stories_without_commits": len(stories_with_no_commits),
            "orphan_commits": len(orphan_commits),
        }
        logger.debug("Audit summary computed: %s", summary)

        return AuditResult(
            summary=summary,
            stories_with_no_commits=stories_with_no_commits,
            orphan_commits=orphan_commits,
            commit_story_mapping=commit_story_mapping,
        )

    @staticmethod
    def _simplify_commit(commit: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "hash": commit.get("hash") or commit.get("id"),
            "message": commit.get("message"),
            "author": commit.get("author", {}).get("user", {}).get("display_name")
            or commit.get("author", {}).get("raw"),
            "date": commit.get("date"),
            "repository": commit.get("repository"),
            "branch": commit.get("branch"),
            "links": commit.get("links"),
        }

"""GitHub Projects v2 helper utilities for Git Historian."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence

import requests

LOGGER = logging.getLogger(__name__)
_GRAPHQL_URL = "https://api.github.com/graphql"


@dataclass
class ProjectStatusItem:
    """Represents an issue captured from a Projects v2 board."""

    number: int
    title: str
    url: str
    status: Optional[str]
    assignees: List[str]


class ProjectsV2Client:
    """Minimal GitHub GraphQL client to query Projects v2 boards."""

    def __init__(self, token: str, session: Optional[requests.Session] = None) -> None:
        if not token:
            raise ValueError("GitHub token is required for Projects v2 queries")
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "release-copilot-git-historian",
            }
        )

    def query_issues_with_status(
        self,
        owner: str,
        repo: str,
        project_name: str,
        status_field: str,
        status_values: Sequence[str],
    ) -> List[ProjectStatusItem]:
        """Return project issues matching the provided status values."""

        project_id = self._resolve_project_id(owner, repo, project_name)
        if not project_id:
            LOGGER.debug("No Projects v2 board named %s found", project_name)
            return []

        normalized_statuses = {value.lower() for value in status_values}
        after: Optional[str] = None
        items: List[ProjectStatusItem] = []
        while True:
            data = self._execute(
                _PROJECT_ITEMS_QUERY,
                {
                    "projectId": project_id,
                    "after": after,
                },
            )
            node = data.get("data", {}).get("node")
            if not node:
                break
            items_data = node.get("items", {})
            for item in items_data.get("nodes", []):
                content = item.get("content") or {}
                if content.get("__typename") != "Issue":
                    continue
                status_name = _extract_status_name(
                    item.get("fieldValues", {}).get("nodes", []), status_field
                )
                if not status_name or status_name.lower() not in normalized_statuses:
                    continue
                assignees = [
                    assignee.get("login")
                    for assignee in (content.get("assignees", {}) or {}).get("nodes", [])
                    if assignee and assignee.get("login")
                ]
                items.append(
                    ProjectStatusItem(
                        number=content.get("number"),
                        title=content.get("title", ""),
                        url=content.get("url", ""),
                        status=status_name,
                        assignees=assignees,
                    )
                )
            page_info = items_data.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                break
            after = page_info.get("endCursor")
        return items

    def _resolve_project_id(self, owner: str, repo: str, project_name: str) -> Optional[str]:
        """Look up the GraphQL node ID for a repository project."""

        data = self._execute(
            _PROJECT_QUERY,
            {
                "owner": owner,
                "name": repo,
            },
        )
        projects = (
            data.get("data", {})
            .get("repository", {})
            .get("projectsV2", {})
            .get("nodes", [])
        )
        for project in projects:
            if (project or {}).get("title") == project_name:
                return project.get("id")
        return None

    def _execute(self, query: str, variables: Dict[str, Optional[str]]) -> Dict[str, object]:
        response = self.session.post(
            _GRAPHQL_URL,
            json={"query": query, "variables": variables},
            timeout=30,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"GitHub GraphQL error {response.status_code}: {response.text}"
            )
        data = response.json()
        if errors := data.get("errors"):
            message = ", ".join(error.get("message", "unknown error") for error in errors)
            raise RuntimeError(f"GitHub GraphQL returned errors: {message}")
        return data


def _extract_status_name(nodes: Iterable[dict], field_name: str) -> Optional[str]:
    for node in nodes:
        if not node:
            continue
        if node.get("__typename") != "ProjectV2ItemFieldSingleSelectValue":
            continue
        field = node.get("field") or {}
        name = field.get("name")
        if name != field_name:
            continue
        return node.get("name")
    return None


_PROJECT_QUERY = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    projectsV2(first: 20) {
      nodes {
        id
        title
      }
    }
  }
}
"""


_PROJECT_ITEMS_QUERY = """
query($projectId: ID!, $after: String) {
  node(id: $projectId) {
    ... on ProjectV2 {
      items(first: 50, after: $after) {
        nodes {
          content {
            __typename
            ... on Issue {
              number
              title
              url
              assignees(first: 10) {
                nodes {
                  login
                }
              }
            }
          }
          fieldValues(first: 20) {
            nodes {
              __typename
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                field {
                  ... on ProjectV2SingleSelectField {
                    name
                  }
                }
              }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
"""

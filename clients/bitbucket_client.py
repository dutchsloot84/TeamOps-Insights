"""Bitbucket Cloud client to retrieve commits for release audits."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

import requests
from requests.auth import HTTPBasicAuth

from releasecopilot.errors import BitbucketRequestError
from releasecopilot.logging_config import get_logger

from .base import BaseAPIClient

logger = get_logger(__name__)


class BitbucketClient(BaseAPIClient):
    BASE_URL = "https://api.bitbucket.org/2.0"

    def __init__(
        self,
        *,
        workspace: str,
        cache_dir: str,
        username: Optional[str] = None,
        app_password: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> None:
        super().__init__(cache_dir)
        self.workspace = workspace
        self.username = username
        self.app_password = app_password
        self.access_token = access_token
        self.session = requests.Session()

    def _get_auth_headers(self) -> Dict[str, str]:
        if self.access_token:
            return {"Authorization": f"Bearer {self.access_token}"}
        return {}

    def _get_auth(self) -> Optional[HTTPBasicAuth]:
        if self.username and self.app_password:
            return HTTPBasicAuth(self.username, self.app_password)
        return None

    def fetch_commits(
        self,
        *,
        repositories: Iterable[str],
        branches: Iterable[str],
        start: datetime,
        end: datetime,
        use_cache: bool = False,
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        all_commits: List[Dict[str, Any]] = []
        cache_keys: List[str] = []
        for repo in repositories:
            for branch in branches:
                cache_key = f"bitbucket_{repo}_{branch}_{start:%Y%m%d}_{end:%Y%m%d}"
                cache_keys.append(cache_key)
                if use_cache:
                    cached = self._load_latest_cache(cache_key)
                    if cached:
                        logger.info("Loaded Bitbucket commits for %s/%s from cache", repo, branch)
                        all_commits.extend(cached["values"])
                        continue

                try:
                    commits = self._fetch_commits_for_branch(repo, branch, start, end)
                except BitbucketRequestError:
                    raise
                except requests.RequestException as exc:  # pragma: no cover - defensive guard
                    context = {
                        "service": "bitbucket",
                        "repository": repo,
                        "branch": branch,
                    }
                    logger.error("Bitbucket request failed", extra=context)
                    raise BitbucketRequestError("Bitbucket request failed", context=context) from exc
                payload = {
                    "retrieved_at": datetime.utcnow().isoformat(),
                    "workspace": self.workspace,
                    "repository": repo,
                    "branch": branch,
                    "values": commits,
                }
                self._cache_response(cache_key, payload)
                all_commits.extend(commits)
        return all_commits, cache_keys

    def _fetch_commits_for_branch(
        self,
        repo_slug: str,
        branch: str,
        start: datetime,
        end: datetime,
    ) -> List[Dict[str, Any]]:
        url = f"{self.BASE_URL}/repositories/{self.workspace}/{repo_slug}/commits/{branch}"
        params = {
            "pagelen": 100,
            "q": f"date >= '{start.isoformat()}' AND date <= '{end.isoformat()}'",
        }
        commits: List[Dict[str, Any]] = []
        while url:
            response = self._request_with_retry(
                session=self.session,
                method="GET",
                url=url,
                logger_context={
                    "service": "bitbucket",
                    "repository": repo_slug,
                    "branch": branch,
                },
                params=params,
                headers=self._get_auth_headers(),
                auth=self._get_auth(),
                timeout=30,
            )
            try:
                response.raise_for_status()
            except requests.RequestException as exc:
                snippet = response.text[:200]
                context = {
                    "service": "bitbucket",
                    "repository": repo_slug,
                    "branch": branch,
                    "status_code": response.status_code,
                    "snippet": snippet,
                }
                logger.error("Bitbucket HTTP error", extra=context)
                raise BitbucketRequestError("Failed to fetch Bitbucket commits", context=context) from exc
            payload = response.json()
            values = payload.get("values", [])
            for commit in values:
                commit.setdefault("repository", repo_slug)
                commit.setdefault("branch", branch)
            commits.extend(values)
            url = payload.get("next")
            params = None  # Subsequent requests include pagination cursor
        return commits

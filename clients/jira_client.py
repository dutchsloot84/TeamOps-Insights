"""Jira API client for fetching issues linked to a fix version."""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from releasecopilot.errors import JiraQueryError, JiraTokenRefreshError
from releasecopilot.logging_config import get_logger

from .base import BaseAPIClient

logger = get_logger(__name__)

TOKEN_REFRESH_ENDPOINT = "https://auth.atlassian.com/oauth/token"


class JiraClient(BaseAPIClient):
    """Wraps the Jira REST API v3 for release auditing operations."""

    def __init__(
        self,
        *,
        base_url: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        token_expiry: Optional[int] = None,
        scope: Optional[List[str]] = None,
        cache_dir: str,
    ) -> None:
        super().__init__(cache_dir)
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.scope = scope or ["read:jira-user", "read:jira-work"]
        self.token_expiry = token_expiry or 0
        self.session = requests.Session()

    # OAuth helpers -----------------------------------------------------
    def _token_is_expired(self) -> bool:
        if not self.access_token:
            return True
        return time.time() >= self.token_expiry - 30

    def _refresh_access_token(self) -> None:
        if not (self.refresh_token and self.client_id and self.client_secret):
            logger.debug("Refresh token flow unavailable; using existing access token")
            return
        payload = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
        }
        try:
            response = self._request_with_retry(
                session=self.session,
                method="POST",
                url=TOKEN_REFRESH_ENDPOINT,
                logger_context={"service": "jira", "operation": "refresh_token"},
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as exc:  # pragma: no cover - defensive
            context = {
                "service": "jira",
                "operation": "refresh_token",
                "status_code": getattr(getattr(exc, "response", None), "status_code", None),
            }
            logger.error("Failed to refresh Jira OAuth token", extra=context)
            raise JiraTokenRefreshError("Failed to refresh Jira OAuth token", context=context) from exc
        token_data = response.json()
        self.access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in", 0)
        self.token_expiry = int(time.time()) + int(expires_in)
        # refresh_token may rotate
        self.refresh_token = token_data.get("refresh_token", self.refresh_token)
        logger.info("Refreshed Jira OAuth token; expires in %s seconds", expires_in)
        self._cache_response("jira_token", token_data)

    def _get_headers(self) -> Dict[str, str]:
        if self._token_is_expired():
            self._refresh_access_token()
        if not self.access_token:
            raise RuntimeError("Jira access token not available")
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    # Fetching ----------------------------------------------------------
    def fetch_issues(
        self,
        *,
        fix_version: str,
        use_cache: bool = False,
        fields: Optional[List[str]] = None,
    ) -> tuple[List[Dict[str, Any]], Optional[Path]]:
        cache_key = f"jira_{fix_version}"
        if use_cache:
            cached_payload = self._load_latest_cache(cache_key)
            if cached_payload:
                logger.info("Loaded Jira issues for %s from cache", fix_version)
                cache_file = self.get_last_cache_file(cache_key)
                return cached_payload["issues"], cache_file

        jql = f"fixVersion = '{fix_version}' ORDER BY key"
        params = {
            "jql": jql,
            "maxResults": 100,
            "fields": ",".join(fields) if fields else "summary,status,assignee,issuetype,customfield_10020",
        }
        start_at = 0
        issues: List[Dict[str, Any]] = []

        while True:
            params["startAt"] = start_at
            url = f"{self.base_url}/rest/api/3/search"
            headers = self._get_headers()
            try:
                response = self._request_with_retry(
                    session=self.session,
                    method="GET",
                    url=url,
                    logger_context={
                        "service": "jira",
                        "operation": "search",
                        "jql": jql,
                        "start_at": start_at,
                    },
                    headers=headers,
                    params=params,
                    timeout=30,
                )
                response.raise_for_status()
            except requests.RequestException as exc:
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                snippet = None
                if getattr(exc, "response", None) is not None:
                    snippet = exc.response.text[:200]
                context = {
                    "service": "jira",
                    "operation": "search",
                    "jql": jql,
                    "status_code": status_code,
                    "start_at": start_at,
                    "snippet": snippet,
                }
                logger.error("Jira search failed", extra=context)
                raise JiraQueryError("Failed to fetch Jira issues", context=context) from exc
            payload = response.json()

            batch = payload.get("issues", [])
            issues.extend(batch)
            if len(batch) == 0 or start_at + params["maxResults"] >= payload.get("total", 0):
                break
            start_at += params["maxResults"]

        cached_payload = {
            "retrieved_at": datetime.utcnow().isoformat(),
            "jql": jql,
            "issues": issues,
        }
        cache_path = self._cache_response(cache_key, cached_payload)
        return issues, cache_path


def compute_fix_version_window(freeze_date: datetime, window_days: int) -> Dict[str, datetime]:
    """Helper used by downstream processing to expose the audit window."""
    return {
        "start": freeze_date - timedelta(days=window_days),
        "end": freeze_date,
    }

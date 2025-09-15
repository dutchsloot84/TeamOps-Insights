"""Utilities for interacting with the Jira REST API."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Iterable, List, Mapping, Optional

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

LOGGER = logging.getLogger(__name__)
TOKEN_URL = "https://auth.atlassian.com/oauth/token"  # nosec B105
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 5


class JiraError(Exception):
    """Base exception for Jira API failures."""


class JiraAuthError(JiraError):
    """Authentication or authorization failure."""


class JiraTransientError(JiraError):
    """Retryable failure returned by Jira."""


class JiraRateLimitError(JiraTransientError):
    """HTTP 429 responses that require waiting before retrying."""


def _normalize_synonym(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").replace("-", " ").split())


def _build_url(base_url: str, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    base = base_url.rstrip("/")
    cleaned_path = path.lstrip("/")
    return f"{base}/{cleaned_path}"


@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    retry=retry_if_exception_type(
        (requests.RequestException, JiraTransientError, JiraRateLimitError)
    ),
    reraise=True,
)
def _request(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Mapping[str, Any]] = None,
    json: Optional[Mapping[str, Any]] = None,
) -> requests.Response:
    params_dict = dict(params) if params is not None else None
    json_dict = dict(json) if json is not None else None
    response = requests.request(
        method,
        url,
        headers=headers,
        params=params_dict,
        json=json_dict,
        timeout=DEFAULT_TIMEOUT,
    )

    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        sleep_for = 5.0
        if retry_after:
            try:
                sleep_for = float(retry_after)
            except ValueError:
                LOGGER.debug("Invalid Retry-After header '%s'", retry_after)
        LOGGER.info("Hit Jira rate limit, sleeping for %.1fs", sleep_for)
        time.sleep(sleep_for)
        raise JiraRateLimitError("Jira rate limit encountered")

    if 500 <= response.status_code < 600:
        raise JiraTransientError(f"Jira 5xx error: {response.status_code}")

    if response.status_code >= 400:
        raise JiraAuthError(f"Jira returned HTTP {response.status_code}: {response.text}")

    return response


@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    retry=retry_if_exception_type(
        (requests.RequestException, JiraTransientError, JiraRateLimitError)
    ),
    reraise=True,
)
def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    """Exchange a refresh token for a short-lived access token."""

    payload = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }

    response = _request("POST", TOKEN_URL, json=payload)
    data = response.json()
    token = data.get("access_token")
    if not token:
        raise JiraAuthError("Access token missing in response")
    return token


def jira_get(base_url: str, token: str, path: str, params: Optional[Mapping[str, Any]] = None):
    """Perform a GET request against the Jira REST API with retry semantics."""

    url = _build_url(base_url, path)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    response = _request("GET", url, headers=headers, params=params)
    return response.json()


def discover_field_map(
    base_url: str,
    token: str,
    synonyms: Optional[Dict[str, Iterable[str]]] = None,
) -> Dict[str, Optional[str]]:
    """Find custom field IDs for the requested synonym sets."""

    synonym_map: Dict[str, Iterable[str]] = synonyms or {
        "acceptance_criteria": ["acceptance criteria", "acceptance-criteria", "ac", "gherkin"],
        "deployment_notes": ["deployment notes", "deploy notes", "release notes (tech)"],
    }

    normalized_targets = {
        key: {_normalize_synonym(value) for value in values} for key, values in synonym_map.items()
    }

    discovered: Dict[str, Optional[str]] = {key: None for key in normalized_targets}
    fields = jira_get(base_url, token, "/rest/api/3/field")

    for field in fields:
        field_name = str(field.get("name", ""))
        normalized_name = _normalize_synonym(field_name)
        field_id = field.get("id") or field.get("key")
        if not field_id:
            continue
        for target, options in normalized_targets.items():
            if normalized_name in options and not discovered[target]:
                discovered[target] = str(field_id)

    return discovered


def search_page(
    base_url: str,
    token: str,
    jql: str,
    fields_csv: str,
    *,
    start_at: int = 0,
    max_results: int = 100,
) -> Dict[str, object]:
    params: Dict[str, Any] = {
        "jql": jql,
        "fields": fields_csv,
        "startAt": start_at,
        "maxResults": max_results,
    }
    return jira_get(base_url, token, "/rest/api/3/search", params=params)


def get_all_comments(
    base_url: str,
    token: str,
    issue_id: str,
    initial_comments: Optional[List[Dict[str, Any]]],
    total: int,
    *,
    page_size: int = 100,
    max_comments: int = 2000,
) -> List[Dict[str, object]]:
    """Fetch the full comment set for an issue, respecting the configured limits."""

    comments: List[Dict[str, Any]] = list(initial_comments or [])
    cap = min(total, max_comments)
    start_at = len(comments)

    while start_at < cap:
        remaining = cap - start_at
        fetch_size = min(page_size, remaining)
        params = {"startAt": start_at, "maxResults": fetch_size}
        response = jira_get(
            base_url,
            token,
            f"/rest/api/3/issue/{issue_id}/comment",
            params=params,
        )
        new_comments = response.get("comments", [])
        if not new_comments:
            break
        comments.extend(new_comments)
        start_at = len(comments)
        if len(new_comments) < fetch_size:
            break

    return comments[:cap]

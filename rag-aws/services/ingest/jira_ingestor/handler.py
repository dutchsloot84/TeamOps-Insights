"""Lambda entrypoint for the Jira ingestion service."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

import boto3
from botocore.exceptions import ClientError
from dateutil import parser as date_parser

from .adf_md import to_markdown
from .jira_api import (
    JiraAuthError,
    JiraRateLimitError,
    JiraTransientError,
    discover_field_map,
    get_all_comments,
    refresh_access_token,
    search_page,
)

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

DEFAULT_LOOKBACK_DAYS = 30
MAX_ISSUES_PER_RUN = 10_000
PAGE_SIZE = 100
PAGE_SLEEP_SECONDS = 0.2
COMMENT_CAP = 2_000

BASE_FIELDS = [
    "summary",
    "description",
    "comment",
    "issuelinks",
    "labels",
    "components",
    "fixVersions",
    "issuetype",
    "status",
    "project",
    "reporter",
    "assignee",
    "created",
    "updated",
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _default_cursor() -> str:
    lookback = _utcnow() - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    return lookback.strftime("%Y-%m-%d %H:%M")


def _parse_updated(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = date_parser.parse(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (ValueError, TypeError) as exc:
        LOGGER.warning("Unable to parse Jira timestamp '%s': %s", value, exc)
        return None


def _format_cursor(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_dict_list(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _rich_text_payload(adf: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "adf": adf if isinstance(adf, dict) else None,
        "markdown": to_markdown(adf if isinstance(adf, dict) else None),
    }


def _normalize_links(links: Iterable[Dict[str, Any]]) -> List[Dict[str, Optional[str]]]:
    normalized: List[Dict[str, Optional[str]]] = []
    for link in links or []:
        link_type = link.get("type", {})
        outward_issue = link.get("outwardIssue")
        inward_issue = link.get("inwardIssue")
        if outward_issue:
            normalized.append(
                {
                    "type": link_type.get("outward") or link_type.get("name"),
                    "direction": "outward",
                    "key": outward_issue.get("key"),
                }
            )
        if inward_issue:
            normalized.append(
                {
                    "type": link_type.get("inward") or link_type.get("name"),
                    "direction": "inward",
                    "key": inward_issue.get("key"),
                }
            )
    return [link for link in normalized if link.get("key")]


def _normalize_comments(comments: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized_comments: List[Dict[str, Any]] = []
    for comment in comments or []:
        body = comment.get("body")
        normalized_comments.append(
            {
                "author": (comment.get("author") or {}).get("displayName"),
                "created": comment.get("created"),
                "adf": body if isinstance(body, dict) else None,
                "markdown": to_markdown(body if isinstance(body, dict) else None),
            }
        )
    return normalized_comments


def normalize_issue(
    issue: Dict[str, Any],
    field_map: Dict[str, Optional[str]],
    base_url: str,
    fetched_at: str,
    *,
    comments: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Normalize a Jira issue into the RAG-friendly schema."""

    fields: Dict[str, Any] = issue.get("fields", {})
    acceptance_field = field_map.get("acceptance_criteria")
    deployment_field = field_map.get("deployment_notes")

    acceptance_adf = fields.get(acceptance_field) if acceptance_field else None
    deployment_adf = fields.get(deployment_field) if deployment_field else None

    comment_field = fields.get("comment")
    if comments is not None:
        comment_source: List[Dict[str, Any]] = list(comments)
    elif isinstance(comment_field, dict):
        comment_source = _as_dict_list(comment_field.get("comments"))
    else:
        comment_source = []

    links_data = _as_dict_list(fields.get("issuelinks"))
    labels_value = fields.get("labels")
    labels = (
        [label for label in labels_value if isinstance(label, str)]
        if isinstance(labels_value, list)
        else []
    )
    component_names = [
        component.get("name")
        for component in _as_dict_list(fields.get("components"))
        if component.get("name")
    ]
    fix_versions = [
        version.get("name")
        for version in _as_dict_list(fields.get("fixVersions"))
        if version.get("name")
    ]

    normalized = {
        "source": "jira",
        "key": issue.get("key"),
        "project": (fields.get("project") or {}).get("key")
        or (fields.get("project") or {}).get("name"),
        "issue_type": (fields.get("issuetype") or {}).get("name"),
        "status": (fields.get("status") or {}).get("name"),
        "summary": fields.get("summary"),
        "description": _rich_text_payload(fields.get("description")),
        "acceptance_criteria": _rich_text_payload(acceptance_adf),
        "deployment_notes": _rich_text_payload(deployment_adf),
        "comments": _normalize_comments(comment_source),
        "links": _normalize_links(links_data),
        "labels": labels,
        "components": component_names,
        "fix_versions": fix_versions,
        "reporter": (fields.get("reporter") or {}).get("displayName"),
        "assignee": (fields.get("assignee") or {}).get("displayName"),
        "created": fields.get("created"),
        "updated": fields.get("updated"),
        "uri": f"{base_url.rstrip('/')}/browse/{issue.get('key')}",
        "fetched_at": fetched_at,
    }
    return normalized


def _write_json_to_s3(s3_client, bucket: str, key: str, payload: Dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    s3_client.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")


def _load_secret(secret_id: str) -> Dict[str, Any]:
    secrets_client = boto3.client("secretsmanager")
    try:
        response = secrets_client.get_secret_value(SecretId=secret_id)
    except ClientError as exc:
        LOGGER.error("Unable to read Jira secret '%s': %s", secret_id, exc)
        raise

    secret_string = response.get("SecretString")
    if secret_string:
        return json.loads(secret_string)
    raise ValueError("SecretString missing from secrets manager response")


def _get_cursor(ssm_client, name: str) -> str:
    try:
        response = ssm_client.get_parameter(Name=name)
        value = response.get("Parameter", {}).get("Value")
        if value:
            return value
    except ssm_client.exceptions.ParameterNotFound:
        LOGGER.info("Cursor parameter '%s' not found; using default lookback", name)
    return _default_cursor()


def _update_cursor(ssm_client, name: str, value: str) -> None:
    ssm_client.put_parameter(Name=name, Value=value, Type="String", Overwrite=True)


def lambda_handler(event: Optional[Dict[str, Any]], context: Any) -> Dict[str, Any]:
    """AWS Lambda handler."""

    try:
        return _run_ingestion()
    except (JiraAuthError, JiraTransientError, JiraRateLimitError) as exc:
        LOGGER.error("Jira ingestion failed: %s", exc)
        raise
    except Exception:  # pragma: no cover - defensive logging
        LOGGER.exception("Unexpected error during Jira ingestion")
        raise


def _run_ingestion() -> Dict[str, Any]:
    s3_bucket = os.environ["S3_BUCKET"]
    secret_id = os.environ["JIRA_OAUTH_SECRET"]
    cursor_param = os.environ.get("CURSOR_PARAM", "/rag/jira/last_sync")

    secret = _load_secret(secret_id)
    client_id = secret["client_id"]
    client_secret = secret["client_secret"]
    refresh_token = secret["refresh_token"]
    base_url = secret["base_url"]

    LOGGER.info("Refreshing Jira access token")
    access_token = refresh_access_token(client_id, client_secret, refresh_token)

    ssm_client = boto3.client("ssm")
    cursor = _get_cursor(ssm_client, cursor_param)
    jql = f'updated >= "{cursor}" ORDER BY updated ASC'
    LOGGER.info("Using JQL: %s", jql)

    field_map = discover_field_map(base_url, access_token)
    if not field_map.get("acceptance_criteria"):
        LOGGER.warning("Acceptance Criteria field not discovered; output will omit this field")
    if not field_map.get("deployment_notes"):
        LOGGER.warning("Deployment Notes field not discovered; output will omit this field")

    fields = list(BASE_FIELDS)
    if field_map.get("acceptance_criteria"):
        fields.append(field_map["acceptance_criteria"])
    if field_map.get("deployment_notes"):
        fields.append(field_map["deployment_notes"])
    fields_csv = ",".join(fields)

    fetched_at = _utcnow().isoformat().replace("+00:00", "Z")
    s3_client = boto3.client("s3")

    latest_updated: Optional[datetime] = None
    issues_processed = 0
    start_at = 0

    while issues_processed < MAX_ISSUES_PER_RUN:
        page = search_page(
            base_url,
            access_token,
            jql,
            fields_csv,
            start_at=start_at,
            max_results=PAGE_SIZE,
        )
        issues = _as_dict_list(page.get("issues"))
        total = _to_int(page.get("total"), 0)
        LOGGER.info("Fetched page startAt=%s count=%s total=%s", start_at, len(issues), total)

        if not issues:
            break

        for issue in issues:
            fields_raw = issue.get("fields")
            fields_data: Dict[str, Any] = fields_raw if isinstance(fields_raw, dict) else {}
            comment_field = fields_data.get("comment")
            comment_info: Dict[str, Any] = comment_field if isinstance(comment_field, dict) else {}
            initial_comments = _as_dict_list(comment_info.get("comments"))
            total_comments = _to_int(comment_info.get("total"), len(initial_comments))
            issue_id = issue.get("id")
            if issue_id is None:
                LOGGER.warning(
                    "Issue %s missing id; skipping extended comment fetch", issue.get("key")
                )
                all_comments = initial_comments[:COMMENT_CAP]
                issue_id_str = issue.get("key") or "unknown"
            else:
                issue_id_str = str(issue_id)
                all_comments = get_all_comments(
                    base_url,
                    access_token,
                    issue_id_str,
                    initial_comments,
                    total_comments,
                    max_comments=COMMENT_CAP,
                )
            if isinstance(comment_field, dict):
                comment_field["comments"] = all_comments

            timestamp = _utcnow().strftime("%Y%m%dT%H%M%SZ")
            issue_key = issue.get("key") or issue_id_str
            raw_key = f"raw/jira/{issue_key}/{issue_id_str}-{timestamp}.json"
            _write_json_to_s3(s3_client, s3_bucket, raw_key, issue)

            normalized = normalize_issue(
                issue,
                field_map,
                base_url,
                fetched_at,
                comments=all_comments,
            )
            normalized_key = f"normalized/jira/{issue_key}.json"
            _write_json_to_s3(s3_client, s3_bucket, normalized_key, normalized)

            updated_value = _parse_updated(fields_data.get("updated"))
            if updated_value and (latest_updated is None or updated_value > latest_updated):
                latest_updated = updated_value

            issues_processed += 1
            if issues_processed >= MAX_ISSUES_PER_RUN:
                LOGGER.warning("Reached per-run issue cap of %s", MAX_ISSUES_PER_RUN)
                break

        start_at += len(issues)
        if start_at >= total:
            break
        time.sleep(PAGE_SLEEP_SECONDS)

    if latest_updated is not None:
        new_cursor = _format_cursor(latest_updated)
        _update_cursor(ssm_client, cursor_param, new_cursor)
    else:
        new_cursor = cursor

    LOGGER.info("Processed %s issues; cursor now %s", issues_processed, new_cursor)
    return {"synced_through": new_cursor, "count": issues_processed}


__all__ = ["lambda_handler", "normalize_issue"]

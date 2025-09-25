"""Lambda handler performing nightly reconciliation between Jira and DynamoDB."""
from __future__ import annotations

import base64
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib import error, parse, request

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError


LOGGER = logging.getLogger()
LOGGER.setLevel(os.getenv("LOG_LEVEL", "INFO"))

TABLE_NAME = os.environ["TABLE_NAME"]
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "https://your-domain.atlassian.net").rstrip("/")
JQL_TEMPLATE = os.getenv("JQL_TEMPLATE", "fixVersion = '{fix_version}' ORDER BY key")
FIX_VERSIONS_RAW = os.getenv("FIX_VERSIONS", "")
MAX_RESULTS = int(os.getenv("MAX_RESULTS", "100"))
JIRA_SECRET_ARN = os.getenv("JIRA_SECRET_ARN")
METRICS_NAMESPACE = os.getenv("METRICS_NAMESPACE", "ReleaseCopilot/JiraSync")
RC_DDB_MAX_ATTEMPTS = int(os.getenv("RC_DDB_MAX_ATTEMPTS", "5"))
RC_DDB_BASE_DELAY = float(os.getenv("RC_DDB_BASE_DELAY", "0.5"))
TOKEN_REFRESH_ENDPOINT = "https://auth.atlassian.com/oauth/token"


_DDB = boto3.resource("dynamodb")
_TABLE = _DDB.Table(TABLE_NAME)
_SECRETS = boto3.client("secretsmanager") if JIRA_SECRET_ARN else None
_CLOUDWATCH = boto3.client("cloudwatch")
_SECRET_CACHE: Optional[Dict[str, Any]] = None


@dataclass
class JiraCredentials:
    """Container for Jira authentication material."""

    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expiry: Optional[int] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    email: Optional[str] = None
    api_token: Optional[str] = None

    @property
    def uses_oauth(self) -> bool:
        return bool(self.client_id and (self.refresh_token or self.access_token))

    @property
    def uses_basic(self) -> bool:
        return bool(self.email and self.api_token)


class JiraSession:
    """Minimal Jira REST session supporting OAuth refresh or basic auth."""

    def __init__(self, base_url: str, credentials: JiraCredentials) -> None:
        self.base_url = base_url.rstrip("/")
        self.creds = credentials
        self.access_token = credentials.access_token
        self.refresh_token = credentials.refresh_token
        self.token_expiry = credentials.token_expiry or 0

    def search(self, jql: str, *, fields: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
        headers = self._build_headers()
        params = {
            "jql": jql,
            "maxResults": MAX_RESULTS,
            "fields": ",".join(fields) if fields else "*all",
        }
        start_at = 0
        issues: List[Dict[str, Any]] = []

        while True:
            params["startAt"] = start_at
            url = f"{self.base_url}/rest/api/3/search?{parse.urlencode(params)}"
            response = _http_request("GET", url, headers=headers)
            payload = json.loads(response)
            batch = payload.get("issues", [])
            issues.extend(batch)
            if not batch or start_at + params["maxResults"] >= payload.get("total", 0):
                break
            start_at += params["maxResults"]

        return issues

    def _build_headers(self) -> Dict[str, str]:
        if self.creds.uses_oauth:
            self._ensure_token()
            if not self.access_token:
                raise RuntimeError("Jira access token unavailable after refresh")
            return {"Authorization": f"Bearer {self.access_token}", "Accept": "application/json"}

        if self.creds.uses_basic:
            token = base64.b64encode(f"{self.creds.email}:{self.creds.api_token}".encode()).decode()
            return {
                "Authorization": f"Basic {token}",
                "Accept": "application/json",
            }

        raise RuntimeError("No Jira credentials available")

    def _ensure_token(self) -> None:
        if not self.creds.uses_oauth:
            return
        if not self.access_token or time.time() >= self.token_expiry - 30:
            self._refresh_token()

    def _refresh_token(self) -> None:
        if not (self.creds.client_id and self.creds.client_secret and self.refresh_token):
            raise RuntimeError("Jira refresh token flow is not configured")
        payload = json.dumps(
            {
                "grant_type": "refresh_token",
                "client_id": self.creds.client_id,
                "client_secret": self.creds.client_secret,
                "refresh_token": self.refresh_token,
            }
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        response = _http_request("POST", TOKEN_REFRESH_ENDPOINT, headers=headers, data=payload)
        token_payload = json.loads(response)
        self.access_token = token_payload.get("access_token")
        self.refresh_token = token_payload.get("refresh_token", self.refresh_token)
        expires_in = int(token_payload.get("expires_in", 0))
        self.token_expiry = int(time.time()) + expires_in
        LOGGER.info("Refreshed Jira OAuth token", extra={"expires_in": expires_in})


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:  # pragma: no cover - context unused
    """Entrypoint for the nightly reconciliation Lambda."""

    LOGGER.info("Starting Jira reconciliation", extra={"event": event})
    stats: List[Dict[str, Any]] = []
    errors: List[str] = []

    try:
        credentials = _load_credentials()
    except Exception as exc:  # pragma: no cover - defensive guard
        LOGGER.exception("Failed to load Jira credentials")
        return _response(500, {"ok": False, "message": str(exc)})

    session = JiraSession(JIRA_BASE_URL, credentials)

    fix_versions = _determine_fix_versions(event)
    if not fix_versions:
        LOGGER.info("No fix versions resolved for reconciliation")
        return _response(200, {"ok": True, "stats": [], "message": "No fix versions configured"})

    for fix_version in fix_versions:
        try:
            jql = JQL_TEMPLATE.format(fixVersion=fix_version, fix_version=fix_version)
        except Exception as exc:
            LOGGER.error("Failed to format JQL template", extra={"error": str(exc), "fix_version": fix_version})
            errors.append(f"format:{fix_version}")
            continue

        try:
            issues = session.search(jql)
        except Exception:  # pragma: no cover - network errors
            LOGGER.exception("Jira search failed", extra={"fix_version": fix_version, "jql": jql})
            errors.append(f"jira:{fix_version}")
            continue

        try:
            result = _reconcile_fix_version(fix_version, issues)
            stats.append(result)
        except Exception:  # pragma: no cover - defensive guard
            LOGGER.exception("Reconciliation failed", extra={"fix_version": fix_version})
            errors.append(f"ddb:{fix_version}")

    _publish_metrics(stats)

    status = 200 if not errors else 207
    return _response(status, {"ok": not errors, "stats": stats, "errors": errors})


def _determine_fix_versions(event: Dict[str, Any]) -> List[str]:
    if isinstance(event, dict):
        explicit = event.get("fixVersions") or event.get("fix_versions")
        if isinstance(explicit, (list, tuple)):
            return [str(value) for value in explicit if str(value).strip()]
    if FIX_VERSIONS_RAW:
        return [part.strip() for part in FIX_VERSIONS_RAW.split(",") if part.strip()]
    return sorted(_discover_fix_versions_from_table())


def _discover_fix_versions_from_table() -> Iterable[str]:
    projection = {"ProjectionExpression": "#fv", "ExpressionAttributeNames": {"#fv": "fix_version"}}
    last_key: Optional[Dict[str, Any]] = None
    seen: set[str] = set()

    while True:
        params = dict(projection)
        if last_key:
            params["ExclusiveStartKey"] = last_key
        response = _execute_with_backoff(_TABLE.scan, params)
        for item in response.get("Items", []):
            value = item.get("fix_version")
            if isinstance(value, str) and value and value not in seen:
                seen.add(value)
                yield value
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break


def _reconcile_fix_version(fix_version: str, jira_issues: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    existing_items = list(_query_fix_version(fix_version))
    existing_by_id = {item.get("issue_id"): item for item in existing_items if item.get("issue_id")}
    seen_issue_ids: set[str] = set()

    created = updated = unchanged = deleted = 0

    for issue in jira_issues:
        issue_id = str(issue.get("id") or issue.get("key"))
        if not issue_id:
            LOGGER.warning("Skipping Jira issue without id", extra={"fix_version": fix_version})
            continue
        seen_issue_ids.add(issue_id)
        item = _build_item(issue, fix_version=fix_version)
        stored = existing_by_id.get(issue_id)
        if stored and stored.get("updated_at") == item.get("updated_at") and not stored.get("deleted"):
            unchanged += 1
            continue
        _put_item_with_retry(item, item.get("updated_at"))
        if stored:
            updated += 1
        else:
            created += 1

    for issue_id, stored in existing_by_id.items():
        if issue_id in seen_issue_ids:
            continue
        if stored.get("deleted"):
            continue
        _mark_deleted(issue_id)
        deleted += 1

    LOGGER.info(
        "Reconciled fix version",
        extra={
            "fix_version": fix_version,
            "created_count": created,
            "updated_count": updated,
            "deleted_count": deleted,
            "unchanged_count": unchanged,
            "total_jira": len(jira_issues),
        },
    )
    return {
        "fixVersion": fix_version,
        "fetched": len(jira_issues),
        "created": created,
        "updated": updated,
        "deleted": deleted,
        "unchanged": unchanged,
    }


def _build_item(issue: Dict[str, Any], *, fix_version: str) -> Dict[str, Any]:
    fields = issue.get("fields") or {}
    fix_versions = [fv.get("name") for fv in fields.get("fixVersions") or [] if fv.get("name")]
    fix_version_value = fix_versions[0] if fix_versions else fix_version or "UNASSIGNED"
    status = (fields.get("status") or {}).get("name", "UNKNOWN")
    assignee = (fields.get("assignee") or {}).get("accountId") or (
        (fields.get("assignee") or {}).get("displayName")
    )
    updated_at = _normalize_timestamp(fields.get("updated") or fields.get("created"))

    return {
        "issue_id": issue.get("id") or issue.get("key"),
        "issue_key": issue.get("key"),
        "project_key": (fields.get("project") or {}).get("key"),
        "status": status,
        "assignee": assignee or "UNASSIGNED",
        "fix_version": fix_version_value,
        "fix_versions": fix_versions,
        "updated_at": updated_at,
        "received_at": _now_iso(),
        "issue": issue,
        "deleted": False,
        "last_event_type": "reconciliation",
    }


def _query_fix_version(fix_version: str) -> Iterable[Dict[str, Any]]:
    params = {
        "IndexName": "FixVersionIndex",
        "KeyConditionExpression": Key("fix_version").eq(fix_version),
    }
    last_key: Optional[Dict[str, Any]] = None
    while True:
        query_params = dict(params)
        if last_key:
            query_params["ExclusiveStartKey"] = last_key
        response = _execute_with_backoff(_TABLE.query, query_params)
        for item in response.get("Items", []):
            yield item
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break


def _mark_deleted(issue_id: str) -> None:
    params = {
        "Key": {"issue_id": issue_id},
        "UpdateExpression": "SET deleted = :true, last_event_type = :evt, received_at = :now",
        "ExpressionAttributeValues": {
            ":true": True,
            ":evt": "reconciliation_missing",
            ":now": _now_iso(),
        },
    }
    _execute_with_backoff(_TABLE.update_item, params)


def _put_item_with_retry(item: Dict[str, Any], updated_at: Optional[str]) -> None:
    condition = "attribute_not_exists(issue_id)"
    values: Dict[str, Any] = {}
    if updated_at:
        condition += " OR updated_at <= :updated"
        values[":updated"] = updated_at
    params: Dict[str, Any] = {"Item": item, "ConditionExpression": condition}
    if values:
        params["ExpressionAttributeValues"] = values
    _execute_with_backoff(_TABLE.put_item, params)


def _execute_with_backoff(action, params: Dict[str, Any]) -> Dict[str, Any]:
    attempt = 1
    while True:
        try:
            return action(**params)
        except ClientError as exc:
            code = (exc.response.get("Error", {}) or {}).get("Code")
            if code == "ConditionalCheckFailedException":
                LOGGER.info("Skipping outdated update", extra={"issue_id": params.get("Item", {}).get("issue_id")})
                return {}
            if code not in {
                "ProvisionedThroughputExceededException",
                "ThrottlingException",
                "RequestLimitExceeded",
                "InternalServerError",
                "TransactionInProgressException",
            } or attempt >= RC_DDB_MAX_ATTEMPTS:
                raise
            delay = RC_DDB_BASE_DELAY * (2 ** (attempt - 1))
            LOGGER.warning("Retrying DynamoDB operation", extra={"attempt": attempt, "delay": round(delay, 2)})
            time.sleep(delay)
            attempt += 1


def _load_credentials() -> JiraCredentials:
    payload = _resolve_secret_payload()
    return JiraCredentials(
        access_token=_first(payload, ["JIRA_ACCESS_TOKEN", "access_token"]),
        refresh_token=_first(payload, ["JIRA_REFRESH_TOKEN", "refresh_token"]),
        token_expiry=_int_or_none(_first(payload, ["JIRA_TOKEN_EXPIRY", "token_expiry"])),
        client_id=_first(payload, ["JIRA_CLIENT_ID", "client_id"]),
        client_secret=_first(payload, ["JIRA_CLIENT_SECRET", "client_secret"]),
        email=_first(payload, ["JIRA_EMAIL", "email", "username"]),
        api_token=_first(payload, ["JIRA_API_TOKEN", "api_token"]),
    )


def _resolve_secret_payload() -> Dict[str, Any]:
    global _SECRET_CACHE
    if _SECRET_CACHE is not None:
        return _SECRET_CACHE
    if not JIRA_SECRET_ARN or _SECRETS is None:
        return {}
    try:
        response = _SECRETS.get_secret_value(SecretId=JIRA_SECRET_ARN)
    except ClientError as exc:  # pragma: no cover - defensive guard
        LOGGER.error("Failed to load Jira secret", extra={"error": str(exc)})
        return {}
    secret_string = response.get("SecretString")
    if not secret_string:
        return {}
    try:
        payload = json.loads(secret_string)
    except json.JSONDecodeError:
        payload = {"value": secret_string}
    _SECRET_CACHE = payload
    return payload


def _publish_metrics(stats: Sequence[Dict[str, Any]]) -> None:
    if not stats:
        return
    metric_data: List[Dict[str, Any]] = []
    for stat in stats:
        fix_version = stat.get("fixVersion") or "UNKNOWN"
        dimensions = [{"Name": "FixVersion", "Value": str(fix_version)}]
        for metric_name in ("created", "updated", "deleted", "unchanged", "fetched"):
            metric_data.append(
                {
                    "MetricName": f"Reconciliation{metric_name.title()}",
                    "Dimensions": dimensions,
                    "Value": float(stat.get(metric_name, 0)),
                    "Unit": "Count",
                }
            )
    try:
        _CLOUDWATCH.put_metric_data(Namespace=METRICS_NAMESPACE, MetricData=metric_data)
    except Exception:  # pragma: no cover - best effort only
        LOGGER.warning("Failed to publish reconciliation metrics", exc_info=True)


def _normalize_timestamp(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(raw / 1000.0, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    text = str(raw)
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError:
            continue
    return text


def _now_iso() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _response(status: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body)}


def _http_request(method: str, url: str, *, headers: Optional[Dict[str, str]] = None, data: Optional[bytes] = None) -> str:
    req = request.Request(url, method=method, headers=headers or {})
    if data is not None:
        req.data = data
    try:
        with request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        LOGGER.error("HTTP error", extra={"url": url, "status": exc.code, "body": body[:200]})
        raise
    except error.URLError as exc:
        LOGGER.error("HTTP connection error", extra={"url": url, "error": str(exc)})
        raise


def _first(payload: Dict[str, Any], keys: Sequence[str]) -> Optional[str]:
    for key in keys:
        value = payload.get(key)
        if value:
            return str(value)
    return None


def _int_or_none(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = ["handler"]

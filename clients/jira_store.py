"""DynamoDB-backed Jira issue store for release audits."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from releasecopilot.errors import JiraQueryError
from releasecopilot.logging_config import get_logger


logger = get_logger(__name__)


_RETRYABLE_DDB_ERRORS = {
    "ProvisionedThroughputExceededException",
    "ThrottlingException",
    "RequestLimitExceeded",
    "InternalServerError",
    "TransactionInProgressException",
}


def _utcnow() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class _QueryConfig:
    index_name: str = "FixVersionIndex"
    consistent_read: bool = False


class JiraIssueStore:
    """Fetch Jira issues from a DynamoDB table maintained by webhook ingestion."""

    def __init__(
        self,
        *,
        table_name: str,
        region_name: Optional[str] = None,
        query_config: _QueryConfig | None = None,
        table_resource: Any | None = None,
    ) -> None:
        if not table_name:
            raise ValueError("DynamoDB table name is required")
        self.table_name = table_name
        self._query_config = query_config or _QueryConfig()
        if table_resource is None:
            resource = boto3.resource("dynamodb", region_name=region_name)
            table_resource = resource.Table(table_name)
        self._table = table_resource
        self._sleep = time.sleep

    # Public API -----------------------------------------------------
    def fetch_issues(
        self,
        *,
        fix_version: str,
        use_cache: bool = False,  # compatibility signature
        fields: Optional[List[str]] = None,
    ) -> tuple[List[Dict[str, Any]], Optional[str]]:
        del use_cache, fields  # Unused but kept for interface parity
        logger.info(
            "Querying cached Jira issues", extra={"table": self.table_name, "fix_version": fix_version}
        )
        try:
            items = list(self._paginate_query(fix_version=fix_version))
        except ClientError as exc:
            self._handle_ddb_error(exc, fix_version)
        except Exception as exc:  # pragma: no cover - defensive
            context = {"table": self.table_name, "fix_version": fix_version, "error": str(exc)}
            logger.exception("Unexpected error querying Jira issue table", extra=context)
            raise JiraQueryError("Failed to query Jira issue store", context=context) from exc

        issues: List[Dict[str, Any]] = []
        for item in items:
            if item.get("deleted"):
                continue
            issue_payload = item.get("issue")
            if not isinstance(issue_payload, dict):
                logger.warning(
                    "Skipping malformed issue item", extra={"issue_id": item.get("issue_id")}
                )
                continue
            issues.append(issue_payload)

        issues.sort(key=lambda issue: issue.get("key") or "")
        logger.info(
            "Loaded %d Jira issues from local store", len(issues), extra={"fix_version": fix_version}
        )
        return issues, None

    # Internal helpers -----------------------------------------------
    def _paginate_query(self, *, fix_version: str) -> Iterable[Dict[str, Any]]:
        if not fix_version:
            logger.warning("Empty fix version provided to JiraIssueStore; returning no items")
            return []

        params: Dict[str, Any] = {
            "IndexName": self._query_config.index_name,
            "KeyConditionExpression": Key("fix_version").eq(fix_version),
            "ScanIndexForward": False,
        }
        if self._query_config.consistent_read:
            params["ConsistentRead"] = True

        last_key: Optional[Dict[str, Any]] = None
        while True:
            if last_key:
                params["ExclusiveStartKey"] = last_key
            response = self._execute_query(params)
            for item in response.get("Items", []):
                yield item
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break

    def _execute_query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        max_attempts = int(os.getenv("RC_DDB_MAX_ATTEMPTS", "5"))
        base_delay = float(os.getenv("RC_DDB_BASE_DELAY", "0.5"))
        attempt = 1
        while True:
            try:
                return self._table.query(**params)
            except ClientError as exc:
                if not self._should_retry(exc) or attempt >= max_attempts:
                    raise
                delay = self._compute_delay(attempt, base_delay)
                logger.warning(
                    "Retrying DynamoDB query", extra={"attempt": attempt, "delay": round(delay, 2)}
                )
                self._sleep(delay)
                attempt += 1

    @staticmethod
    def _compute_delay(attempt: int, base_delay: float) -> float:
        jitter = base_delay * 0.25
        return base_delay * (2 ** (attempt - 1)) + jitter

    @staticmethod
    def _should_retry(error: ClientError) -> bool:
        code = (error.response.get("Error", {}) or {}).get("Code")
        return code in _RETRYABLE_DDB_ERRORS

    def _handle_ddb_error(self, error: ClientError, fix_version: str) -> None:
        code = (error.response.get("Error", {}) or {}).get("Code")
        message = (error.response.get("Error", {}) or {}).get("Message")
        context = {
            "table": self.table_name,
            "fix_version": fix_version,
            "code": code,
            "error_message": message,
            "request_id": error.response.get("ResponseMetadata", {}).get("RequestId"),
            "captured_at": _utcnow(),
        }
        logger.error("DynamoDB query failed", extra=context)
        raise JiraQueryError("Failed to query Jira issue store", context=context) from error


__all__ = ["JiraIssueStore"]


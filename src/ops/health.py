"""Readiness checks for ReleaseCopilot operational environments."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, MutableMapping

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from releasecopilot.logging_config import get_logger
from releasecopilot.uploader import build_s3_client, put_object

LOGGER = get_logger(__name__)

HEALTH_VERSION = "health.v1"


@dataclass(frozen=True)
class ReadinessClients:
    """Container for AWS clients used during readiness checks."""

    secrets: Any | None = None
    dynamodb: Any | None = None
    s3: Any | None = None


@dataclass(frozen=True)
class ReadinessOptions:
    """Configuration parameters driving the readiness workflow."""

    region: str | None
    bucket: str | None
    prefix: str | None
    table_name: str | None
    secrets: Mapping[str, str]
    webhook_secret_id: str | None
    webhook_env_present: bool
    dry_run: bool = False
    clients: ReadinessClients | None = None


@dataclass
class CheckResult:
    """Normalized representation of a readiness check outcome."""

    status: str
    resource: str | None = None
    reason: str | None = None

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"status": self.status}
        if self.resource:
            payload["resource"] = self.resource
        if self.reason:
            payload["reason"] = self.reason
        return payload


@dataclass
class ReadinessReport:
    """Structured payload summarising readiness checks."""

    version: str
    timestamp: str
    overall: str
    checks: Dict[str, Dict[str, Any]]
    cleanup_warning: str | None = None
    dry_run: bool = False

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "version": self.version,
            "timestamp": self.timestamp,
            "overall": self.overall,
            "checks": self.checks,
        }
        if self.cleanup_warning:
            payload["cleanup_warning"] = self.cleanup_warning
        if self.dry_run:
            payload["dry_run"] = True
        return payload

    def is_success(self) -> bool:
        """Return ``True`` when all checks succeeded."""

        return self.overall == "pass"


def run_readiness(options: ReadinessOptions) -> ReadinessReport:
    """Execute readiness checks returning a structured report."""

    timestamp = datetime.now(timezone.utc).isoformat()
    clients = options.clients or _build_clients(options.region)
    cleanup_messages: list[str] = []

    secret_result, secret_state = _check_secrets(options, clients)
    dynamo_result, dynamo_warning = _check_dynamodb(options, clients)
    if dynamo_warning:
        cleanup_messages.append(dynamo_warning)
    s3_result, s3_warning = _check_s3(options, clients)
    if s3_warning:
        cleanup_messages.append(s3_warning)
    webhook_result = _check_webhook(options, clients, secret_state)

    checks = {
        "secrets": secret_result.as_dict(),
        "dynamodb": dynamo_result.as_dict(),
        "s3": s3_result.as_dict(),
        "webhook_secret": webhook_result.as_dict(),
    }

    overall = "pass"
    for result in (secret_result, dynamo_result, s3_result, webhook_result):
        if result.status != "pass":
            overall = "fail"
            break

    report = ReadinessReport(
        version=HEALTH_VERSION,
        timestamp=timestamp,
        overall=overall,
        checks=checks,
        cleanup_warning="; ".join(cleanup_messages) if cleanup_messages else None,
        dry_run=options.dry_run,
    )
    return report


def _build_clients(region: str | None) -> ReadinessClients:
    return ReadinessClients(
        secrets=boto3.client("secretsmanager", region_name=region),
        dynamodb=boto3.client("dynamodb", region_name=region),
        s3=build_s3_client(region_name=region),
    )


def _check_secrets(
    options: ReadinessOptions, clients: ReadinessClients
) -> tuple[CheckResult, MutableMapping[str, bool]]:
    secret_status: MutableMapping[str, bool] = {}
    if not options.secrets:
        return CheckResult("pass", resource="secretsmanager://none", reason="No secrets requested"), secret_status

    resource = ", ".join(
        f"{name}={secret_id}" for name, secret_id in sorted(options.secrets.items())
    )
    if options.dry_run:
        LOGGER.info("Skipping secrets check (dry-run)", extra={"secrets": list(options.secrets.keys())})
        for secret_id in options.secrets.values():
            secret_status[secret_id] = True
        return (
            CheckResult("pass", resource=f"secretsmanager://{resource}", reason="Dry-run"),
            secret_status,
        )

    failures: list[str] = []
    for name, secret_id in options.secrets.items():
        try:
            response = clients.secrets.get_secret_value(SecretId=secret_id)
        except (BotoCoreError, ClientError) as exc:
            LOGGER.error(
                "Failed to read secret",
                extra={"secret_name": name, "secret_id": secret_id, "error": str(exc)},
            )
            failures.append(f"{name}: unable to read secret ({exc.__class__.__name__})")
            secret_status[secret_id] = False
            continue

        has_payload = bool(response.get("SecretString") or response.get("SecretBinary"))
        secret_status[secret_id] = has_payload
        if not has_payload:
            LOGGER.error(
                "Secret payload was empty",
                extra={"secret_name": name, "secret_id": secret_id},
            )
            failures.append(f"{name}: secret payload empty")
        else:
            LOGGER.info(
                "Secret validated",
                extra={"secret_name": name, "secret_id": secret_id},
            )

    status = "fail" if failures else "pass"
    reason = "; ".join(failures) if failures else None
    return CheckResult(status, resource=f"secretsmanager://{resource}", reason=reason), secret_status


def _check_webhook(
    options: ReadinessOptions,
    clients: ReadinessClients,
    secret_status: Mapping[str, bool],
) -> CheckResult:
    env_name = "WEBHOOK_SECRET"
    if options.dry_run:
        return CheckResult("pass", resource="webhook-secret", reason="Dry-run")

    if options.webhook_env_present:
        LOGGER.info("Webhook secret resolved from environment", extra={"source": env_name})
        return CheckResult("pass", resource=f"env://{env_name}")

    secret_id = options.webhook_secret_id
    if not secret_id:
        LOGGER.error("Webhook secret is not configured")
        return CheckResult("fail", resource="webhook-secret", reason="Webhook secret not configured")

    if secret_status.get(secret_id) is True:
        return CheckResult("pass", resource=f"secretsmanager://{secret_id}")
    if secret_status.get(secret_id) is False:
        return CheckResult("fail", resource=f"secretsmanager://{secret_id}", reason="Webhook secret payload empty")

    try:
        response = clients.secrets.get_secret_value(SecretId=secret_id)
    except (BotoCoreError, ClientError) as exc:
        LOGGER.error(
            "Failed to resolve webhook secret",
            extra={"secret_id": secret_id, "error": str(exc)},
        )
        return CheckResult("fail", resource=f"secretsmanager://{secret_id}", reason="Unable to fetch webhook secret")

    has_payload = bool(response.get("SecretString") or response.get("SecretBinary"))
    if not has_payload:
        LOGGER.error(
            "Webhook secret payload empty",
            extra={"secret_id": secret_id},
        )
        return CheckResult("fail", resource=f"secretsmanager://{secret_id}", reason="Webhook secret payload empty")

    return CheckResult("pass", resource=f"secretsmanager://{secret_id}")


def _check_dynamodb(
    options: ReadinessOptions, clients: ReadinessClients
) -> tuple[CheckResult, str | None]:
    table_name = options.table_name
    if not table_name:
        LOGGER.error("DynamoDB table name is not configured")
        return CheckResult("fail", resource="dynamodb://", reason="Missing table name"), None

    if options.dry_run:
        return CheckResult("pass", resource=f"dynamodb://{table_name}", reason="Dry-run"), None

    client = clients.dynamodb
    try:
        description = client.describe_table(TableName=table_name)["Table"]
    except (BotoCoreError, ClientError) as exc:
        LOGGER.error(
            "Failed to describe DynamoDB table",
            extra={"table_name": table_name, "error": str(exc)},
        )
        return (
            CheckResult("fail", resource=f"dynamodb://{table_name}", reason="DescribeTable failed"),
            None,
        )

    key_schema = description.get("KeySchema") or []
    attr_defs = {definition["AttributeName"]: definition["AttributeType"] for definition in description.get("AttributeDefinitions", [])}
    if not key_schema:
        LOGGER.error("Table key schema missing", extra={"table_name": table_name})
        return (
            CheckResult("fail", resource=f"dynamodb://{table_name}", reason="Missing key schema"),
            None,
        )

    key_types = {element.get("KeyType") for element in key_schema}
    if "HASH" not in key_types or "RANGE" not in key_types:
        LOGGER.error(
            "Table key schema incomplete",
            extra={"table_name": table_name, "key_schema": key_schema},
        )
        return (
            CheckResult("fail", resource=f"dynamodb://{table_name}", reason="Missing range key"),
            None,
        )

    sentinel = f"rc-health-{uuid.uuid4().hex}"
    item: Dict[str, Dict[str, str]] = {}
    for index, element in enumerate(key_schema):
        name = element.get("AttributeName")
        attr_type = attr_defs.get(name, "S")
        seed = f"{sentinel}-{index}"
        item[name] = _ddb_attribute(attr_type, seed)

    try:
        client.put_item(TableName=table_name, Item=item)
        LOGGER.info("Wrote DynamoDB sentinel item", extra={"table_name": table_name})
    except (BotoCoreError, ClientError) as exc:
        LOGGER.error(
            "Failed to write DynamoDB sentinel item",
            extra={"table_name": table_name, "error": str(exc)},
        )
        return (
            CheckResult("fail", resource=f"dynamodb://{table_name}", reason="PutItem failed"),
            None,
        )

    cleanup_warning: str | None = None
    try:
        client.delete_item(TableName=table_name, Key=item)
    except (BotoCoreError, ClientError) as exc:
        cleanup_warning = f"Failed to delete DynamoDB sentinel ({exc.__class__.__name__})"
        LOGGER.warning(
            "Failed to delete DynamoDB sentinel",
            extra={"table_name": table_name, "error": str(exc)},
        )
    else:
        LOGGER.info("Deleted DynamoDB sentinel item", extra={"table_name": table_name})

    return CheckResult("pass", resource=f"dynamodb://{table_name}"), cleanup_warning


def _ddb_attribute(attr_type: str, sentinel: str) -> Dict[str, str]:
    if attr_type == "N":
        return {"N": str(int(time.time()))}
    if attr_type == "B":
        return {"B": sentinel.encode("utf-8")}
    return {"S": sentinel}


def _check_s3(
    options: ReadinessOptions, clients: ReadinessClients
) -> tuple[CheckResult, str | None]:
    bucket = options.bucket
    if not bucket:
        LOGGER.error("S3 bucket is not configured")
        return CheckResult("fail", resource="s3://", reason="Missing bucket"), None

    prefix = options.prefix.strip("/") if options.prefix else ""
    if options.dry_run:
        resource = f"s3://{bucket}/{prefix}" if prefix else f"s3://{bucket}"
        return CheckResult("pass", resource=resource, reason="Dry-run"), None

    client = clients.s3
    sentinel = uuid.uuid4().hex
    key_parts = [part for part in (prefix, "health", "readiness", f"{sentinel}.txt") if part]
    key = "/".join(key_parts)
    resource = f"s3://{bucket}/{key}"

    try:
        put_object(
            bucket=bucket,
            key=key,
            body="releasecopilot-readiness",
            client=client,
        )
        LOGGER.info("Uploaded S3 sentinel object", extra={"bucket": bucket, "key": key})
    except (BotoCoreError, ClientError) as exc:
        LOGGER.error(
            "Failed to upload S3 sentinel object",
            extra={"bucket": bucket, "key": key, "error": str(exc)},
        )
        return CheckResult("fail", resource=resource, reason="PutObject failed"), None

    cleanup_warning: str | None = None
    try:
        client.delete_object(Bucket=bucket, Key=key)
        LOGGER.info("Deleted S3 sentinel object", extra={"bucket": bucket, "key": key})
    except (BotoCoreError, ClientError) as exc:
        cleanup_warning = f"Failed to delete S3 sentinel ({exc.__class__.__name__})"
        LOGGER.warning(
            "Failed to delete S3 sentinel object",
            extra={"bucket": bucket, "key": key, "error": str(exc)},
        )

    return CheckResult("pass", resource=resource), cleanup_warning


__all__ = [
    "HEALTH_VERSION",
    "ReadinessClients",
    "ReadinessOptions",
    "ReadinessReport",
    "run_readiness",
]

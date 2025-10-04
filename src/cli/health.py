"""CLI helpers for the ``rc health`` command."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from releasecopilot.logging_config import get_logger

from ..config.loader import (
    Defaults,
    get_aws_region,
    get_dynamodb_table,
    get_s3_destination,
    get_secrets_mapping,
    load_config,
)
from ..ops.health import ReadinessOptions, run_readiness

LOGGER = get_logger(__name__)


class HealthCommandError(RuntimeError):
    """Raised when health command execution fails."""


def register_health_parser(subparsers: argparse._SubParsersAction, defaults: Defaults) -> None:
    parser = subparsers.add_parser(
        "health",
        help="Operational health checks",
    )
    parser.add_argument(
        "--readiness",
        action="store_true",
        help="Run readiness checks against AWS dependencies",
    )
    parser.add_argument(
        "--bucket",
        help="Override S3 bucket or s3://bucket/prefix for the sentinel probe",
    )
    parser.add_argument(
        "--table",
        help="Override DynamoDB table name for the sentinel probe",
    )
    parser.add_argument(
        "--secrets",
        help="Comma-separated logical secret names or ARNs to validate",
    )
    parser.add_argument(
        "--json",
        help="Write readiness JSON output to the provided path instead of stdout",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Describe planned checks without calling AWS APIs",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    parser.add_argument(
        "--config",
        help="Optional settings file override (defaults to config/settings.yaml)",
        default=str(defaults.settings_path),
    )


def run_health_command(args: argparse.Namespace, defaults: Defaults) -> int:
    if not args.readiness:
        raise HealthCommandError("Specify --readiness to run readiness checks")

    config = load_config(args.config)
    region = get_aws_region(config)
    bucket, prefix = _resolve_bucket(args.bucket, config)
    table_name = args.table or get_dynamodb_table(config)
    secrets_map = get_secrets_mapping(config)
    secrets = _select_secrets(args.secrets, secrets_map)

    webhook_secret_id = os.getenv("WEBHOOK_SECRET_ARN") or secrets_map.get("webhook")
    webhook_env_present = bool(os.getenv("WEBHOOK_SECRET"))

    options = ReadinessOptions(
        region=region,
        bucket=bucket,
        prefix=prefix,
        table_name=table_name,
        secrets=secrets,
        webhook_secret_id=webhook_secret_id,
        webhook_env_present=webhook_env_present,
        dry_run=args.dry_run,
    )

    LOGGER.debug(
        "Executing readiness checks",
        extra={
            "bucket": bucket,
            "prefix": prefix,
            "table": table_name,
            "secrets": list(secrets.keys()),
            "webhook_secret": bool(webhook_secret_id),
            "dry_run": args.dry_run,
        },
    )

    report = run_readiness(options)
    payload = json.dumps(report.as_dict(), indent=2)

    if args.json:
        output_path = Path(args.json).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
        LOGGER.info("Wrote readiness output", extra={"path": str(output_path)})
    else:
        print(payload)

    return 0 if report.is_success() else 1


def _resolve_bucket(value: str | None, config: dict) -> tuple[str | None, str | None]:
    if value:
        if value.startswith("s3://"):
            trimmed = value[5:]
            if "/" in trimmed:
                bucket, prefix = trimmed.split("/", 1)
                return bucket, prefix
            return trimmed, None
        return value, None

    bucket, prefix = get_s3_destination(config)
    return bucket, prefix


def _select_secrets(override: str | None, configured: dict[str, str]) -> dict[str, str]:
    if not override:
        return dict(configured)

    selected: dict[str, str] = {}
    for entry in override.split(","):
        name = entry.strip()
        if not name:
            continue
        secret_id = configured.get(name)
        if secret_id:
            selected[name] = secret_id
        else:
            selected[name] = name
    return selected


__all__ = ["register_health_parser", "run_health_command", "HealthCommandError"]

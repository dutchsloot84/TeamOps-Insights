"""CDK application entrypoint for the ReleaseCopilot infrastructure."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

from aws_cdk import App, Environment

try:
    from .core_stack import CoreStack
except ImportError:  # pragma: no cover
    from core_stack import CoreStack  # type: ignore


def _context(app: App, key: str, default: Any) -> Any:
    value = app.node.try_get_context(key)
    return default if value is None else value


def _optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _load_context(app: App) -> Dict[str, Any]:
    return {
        "env": str(_context(app, "env", "dev")),
        "region": str(_context(app, "region", "us-west-2")),
        "bucketBase": str(_context(app, "bucketBase", "releasecopilot-artifacts")),
        "account": _optional_str(_context(app, "account", None)),
        "jiraSecretArn": str(_context(app, "jiraSecretArn", "")),
        "bitbucketSecretArn": str(_context(app, "bitbucketSecretArn", "")),
        "scheduleEnabled": _to_bool(_context(app, "scheduleEnabled", False)),
        "scheduleCron": str(_context(app, "scheduleCron", "")),
        "lambdaAssetPath": str(_context(app, "lambdaAssetPath", "../../dist")),
        "lambdaHandler": str(_context(app, "lambdaHandler", "main.handler")),
        "lambdaTimeoutSec": int(_context(app, "lambdaTimeoutSec", 180)),
        "lambdaMemoryMb": int(_context(app, "lambdaMemoryMb", 512)),
        "jiraWebhookSecretArn": str(_context(app, "jiraWebhookSecretArn", "")),
    }


def _aws_identity(region_hint: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    try:
        import boto3  # type: ignore
    except ImportError:  # pragma: no cover - boto3 optional for local synth
        return None, None

    try:
        session = boto3.session.Session(region_name=region_hint)
    except Exception:  # pragma: no cover - misconfigured boto3 session
        return None, region_hint

    resolved_region = session.region_name or region_hint

    try:
        sts = session.client("sts")
        identity = sts.get_caller_identity()
    except Exception:  # pragma: no cover - credentials missing/invalid
        return None, resolved_region

    return identity.get("Account"), resolved_region


def _resolve_environment(app: App, context: Dict[str, Any]) -> Tuple[Optional[str], str]:
    account = _optional_str(context.get("account"))
    region = _optional_str(context.get("region"))

    if not region:
        for candidate in (
            os.getenv("CDK_DEFAULT_REGION"),
            os.getenv("AWS_REGION"),
            os.getenv("AWS_DEFAULT_REGION"),
        ):
            region = _optional_str(candidate)
            if region:
                break

    if not account:
        account_from_context = _optional_str(app.node.try_get_context("account"))
        if account_from_context:
            account = account_from_context

    boto_account, boto_region = _aws_identity(region)
    if not region and boto_region:
        region = boto_region
    if not account and boto_account:
        account = boto_account

    if not account:
        for candidate in (
            os.getenv("CDK_DEFAULT_ACCOUNT"),
            os.getenv("AWS_ACCOUNT_ID"),
            os.getenv("ACCOUNT_ID"),
        ):
            account = _optional_str(candidate)
            if account:
                break

    if not region:
        region = "us-west-2"

    return account, region


app = App()
context = _load_context(app)

account_id, region = _resolve_environment(app, context)

bucket_suffix = f"-{account_id}" if account_id else ""
bucket_name = f"{context['bucketBase']}{bucket_suffix}"

environment = Environment(account=account_id, region=region)

CoreStack(
    app,
    f"ReleaseCopilot-{context['env']}-Core",
    env=environment,
    bucket_name=bucket_name,
    jira_secret_arn=context["jiraSecretArn"] or None,
    bitbucket_secret_arn=context["bitbucketSecretArn"] or None,
    lambda_asset_path=context["lambdaAssetPath"],
    lambda_handler=context["lambdaHandler"],
    lambda_timeout_sec=context["lambdaTimeoutSec"],
    lambda_memory_mb=context["lambdaMemoryMb"],
    schedule_enabled=context["scheduleEnabled"],
    schedule_cron=context["scheduleCron"],
    jira_webhook_secret_arn=context["jiraWebhookSecretArn"] or None,
)

app.synth()

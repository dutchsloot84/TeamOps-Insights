"""CDK application entrypoint for the ReleaseCopilot infrastructure."""
from __future__ import annotations

import os
from typing import Any, Dict

from aws_cdk import App, Environment

try:
    from .core_stack import CoreStack
except ImportError:  # pragma: no cover
    from core_stack import CoreStack  # type: ignore


def _context(app: App, key: str, default: Any) -> Any:
    value = app.node.try_get_context(key)
    return default if value is None else value


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
        "jiraSecretArn": str(_context(app, "jiraSecretArn", "")),
        "bitbucketSecretArn": str(_context(app, "bitbucketSecretArn", "")),
        "scheduleEnabled": _to_bool(_context(app, "scheduleEnabled", False)),
        "scheduleCron": str(_context(app, "scheduleCron", "")),
        "lambdaAssetPath": str(_context(app, "lambdaAssetPath", "../../dist")),
        "lambdaHandler": str(_context(app, "lambdaHandler", "main.handler")),
        "lambdaTimeoutSec": int(_context(app, "lambdaTimeoutSec", 180)),
        "lambdaMemoryMb": int(_context(app, "lambdaMemoryMb", 512)),
    }


app = App()
context = _load_context(app)

account_id = os.getenv("CDK_DEFAULT_ACCOUNT")
if not account_id:
    raise RuntimeError("CDK_DEFAULT_ACCOUNT environment variable must be set for synthesis")

bucket_name = f"{context['bucketBase']}-{account_id}"

environment = Environment(account=account_id, region=context["region"])

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
)

app.synth()

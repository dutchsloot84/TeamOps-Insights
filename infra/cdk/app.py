"""CDK application entrypoint for the Release Copilot core stack."""
from __future__ import annotations

import os
from typing import Any

from aws_cdk import App, Aws, Environment

from .core_stack import CoreStack


def _context(app: App, key: str, default: Any | None = None) -> Any:
    value = app.node.try_get_context(key)
    if value is None:
        return default
    return value


app = App()

env_name = str(_context(app, "env", "dev"))
region = str(_context(app, "region", os.getenv("CDK_DEFAULT_REGION") or "us-west-2"))

jira_secret_arn = str(_context(app, "jiraSecretArn", "") or "")
bitbucket_secret_arn = str(_context(app, "bitbucketSecretArn", "") or "")
lambda_asset_path = str(_context(app, "lambdaAssetPath", "../../dist") or "../../dist")
lambda_handler = str(_context(app, "lambdaHandler", "main.handler") or "main.handler")
rc_s3_prefix = str(_context(app, "rcS3Prefix", "releasecopilot") or "releasecopilot")
lambda_timeout_sec = int(_context(app, "lambdaTimeoutSec", 180) or 180)
lambda_memory_mb = int(_context(app, "lambdaMemoryMb", 512) or 512)

raw_bucket_name = _context(app, "bucketName", "") or ""
if raw_bucket_name:
    bucket_name = str(raw_bucket_name)
else:
    account_from_env = os.getenv("CDK_DEFAULT_ACCOUNT")
    if account_from_env:
        bucket_name = f"releasecopilot-artifacts-{account_from_env}"
    else:
        bucket_name = f"releasecopilot-artifacts-{Aws.ACCOUNT_ID}"

aws_environment = Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=region,
)

CoreStack(
    app,
    f"ReleaseCopilot-{env_name}-Core",
    env=aws_environment,
    bucket_name=bucket_name,
    jira_secret_arn=jira_secret_arn or None,
    bitbucket_secret_arn=bitbucket_secret_arn or None,
    lambda_asset_path=lambda_asset_path,
    lambda_handler=lambda_handler,
    rc_s3_prefix=rc_s3_prefix,
    lambda_timeout_sec=lambda_timeout_sec,
    lambda_memory_mb=lambda_memory_mb,
)

app.synth()

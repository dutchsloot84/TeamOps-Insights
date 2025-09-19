"""CDK application entrypoint for the audit core infrastructure."""
from __future__ import annotations

import json
import os
from typing import Any, Mapping

from aws_cdk import App, Environment

from .core_stack import CoreStack


def _context(app: App, key: str, default: Any | None = None) -> Any:
    value = app.node.try_get_context(key)
    if value is None:
        return default
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass
    return value


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


app = App()

env_name = str(_context(app, "env", "dev"))
project = str(_context(app, "project", "releasecopilot"))
bucket_base = str(_context(app, "bucketBase", f"{project}-audit"))
report_prefix = str(_context(app, "reportPrefix", "reports/"))
raw_prefix = str(_context(app, "rawPrefix", "raw/"))
secret_names: Mapping[str, str] = _context(app, "secrets", {}) or {}
log_level = str(_context(app, "logLevel", "INFO"))
fix_version = _context(app, "fixVersion")
lambda_module = str(_context(app, "lambdaModule", "aws.core_handler"))
schedule_enabled = _as_bool(_context(app, "scheduleEnabled", False))
schedule_cron = str(_context(app, "scheduleCron", "cron(30 8 * * ? *)"))
retain_bucket = _as_bool(_context(app, "retainBucket", env_name == "prod"))

enable_schedule = schedule_enabled or _as_bool(
    os.getenv("ENABLE_EVENTBRIDGE", "0")
)

region = str(_context(app, "region", os.getenv("CDK_DEFAULT_REGION") or "us-west-2"))

aws_env = Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=region,
)

CoreStack(
    app,
    f"{project}-{env_name}-core",
    env=aws_env,
    env_name=env_name,
    bucket_base=bucket_base,
    secret_names=secret_names,
    report_prefix=report_prefix,
    raw_prefix=raw_prefix,
    enable_schedule=enable_schedule,
    schedule_expression=schedule_cron,
    retain_bucket=retain_bucket,
    fix_version=fix_version,
    log_level=log_level,
    lambda_module=lambda_module,
)

app.synth()

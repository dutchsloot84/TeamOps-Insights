"""CDK application entrypoint for the audit core infrastructure."""
from __future__ import annotations

import os
from typing import Any, Mapping

from aws_cdk import App, Environment

from .core_stack import CoreStack


def _context(app: App, key: str, default: Any | None = None) -> Any:
    value = app.node.try_get_context(key)
    return value if value is not None else default


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
enable_schedule = _as_bool(_context(app, "enableEventbridge", False) or os.getenv("ENABLE_EVENTBRIDGE"))

aws_env = Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("CDK_DEFAULT_REGION"),
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
    fix_version=fix_version,
    log_level=log_level,
    lambda_module=lambda_module,
)

app.synth()

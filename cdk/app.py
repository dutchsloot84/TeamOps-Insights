#!/usr/bin/env python3
from __future__ import annotations

import os

import aws_cdk as cdk

from stacks.core_stack import CoreStack
from stacks.lambda_stack import LambdaStack


app = cdk.App()
project = app.node.try_get_context("projectName") or "releasecopilot-ai"
region = (
    app.node.try_get_context("region")
    or os.environ.get("CDK_DEFAULT_REGION")
    or app.node.try_get_context("defaultRegion")
    or "us-west-2"
)
account = os.environ.get("CDK_DEFAULT_ACCOUNT")

env = cdk.Environment(account=account, region=region)

core = CoreStack(app, f"{project}-core", project_name=project, env=env)

enable_schedule = os.environ.get("ENABLE_EVENTBRIDGE", "0") == "1"

LambdaStack(
    app,
    f"{project}-lambda",
    project_name=project,
    bucket=core.artifacts_bucket,
    secret=core.oauth_secret,
    lambda_role=core.lambda_role,
    enable_schedule=enable_schedule,
    env=env,
)

app.synth()

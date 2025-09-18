"""Compute stack hosting the audit Lambda function."""
from __future__ import annotations

from pathlib import Path

from aws_cdk import (
    Duration,
    Stack,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_lambda as _lambda,
)
from constructs import Construct


class LambdaStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        project_name: str,
        bucket,
        secret,
        lambda_role: iam.IRole,
        enable_schedule: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        code_path = Path(__file__).resolve().parents[2] / "dist" / "lambda"
        code_path.mkdir(parents=True, exist_ok=True)

        self.audit_lambda = _lambda.Function(
            self,
            "AuditLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="lambda_handler.lambda_handler",
            code=_lambda.Code.from_asset(str(code_path)),
            timeout=Duration.minutes(15),
            memory_size=1024,
            role=lambda_role,
            environment={
                "ARTIFACTS_BUCKET": bucket.bucket_name,
                "OAUTH_SECRET_ARN": secret.secret_arn,
                "PROJECT_NAME": project_name,
            },
        )

        bucket.grant_put(self.audit_lambda)
        secret.grant_read(self.audit_lambda)

        self.schedule = events.Rule(
            self,
            "AuditSchedule",
            schedule=events.Schedule.cron(minute="0", hour="3"),
            enabled=enable_schedule,
        )
        self.schedule.add_target(targets.LambdaFunction(self.audit_lambda))

"""Core infrastructure stack for Release Copilot audit workflows."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_s3 as s3,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct


class CoreStack(Stack):
    """Provision the foundational audit resources."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        env_name: str,
        bucket_base: str,
        secret_names: Mapping[str, str],
        report_prefix: str = "reports/",
        raw_prefix: str = "raw/",
        enable_schedule: bool = False,
        schedule_expression: str = "cron(30 8 * * ? *)",
        retain_bucket: bool = False,
        fix_version: str | None = None,
        log_level: str = "INFO",
        lambda_module: str = "aws.core_handler",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self._report_prefix = self._normalise_prefix(report_prefix)
        self._raw_prefix = self._normalise_prefix(raw_prefix)

        bucket_name = f"{bucket_base}-{env_name}"
        removal_policy = RemovalPolicy.RETAIN if retain_bucket else RemovalPolicy.DESTROY

        self.bucket = s3.Bucket(
            self,
            "AuditArtifactsBucket",
            bucket_name=bucket_name,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=removal_policy,
        )

        lifecycle_transition = s3.Transition(
            storage_class=s3.StorageClass.INTELLIGENT_TIERING,
            transition_after=Duration.days(30),
        )
        for prefix, rule_id in ((self._raw_prefix, "RawToIa"), (self._report_prefix, "ReportsToIa")):
            self.bucket.add_lifecycle_rule(
                id=rule_id,
                prefix=prefix,
                transitions=[lifecycle_transition],
                abort_incomplete_multipart_upload_after=Duration.days(7),
            )

        self.secrets: dict[str, secretsmanager.Secret] = {}
        for key, name in secret_names.items():
            safe_id = f"{key.title().replace('/', '').replace('-', '')}Secret"
            secret = secretsmanager.Secret(
                self,
                safe_id,
                secret_name=name,
                description=f"OAuth credential for {key}",
            )
            self.secrets[key] = secret

        self.lambda_role = iam.Role(
            self,
            "AuditLambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Execution role for Release Copilot audit Lambda",
        )

        self.lambda_role.attach_inline_policy(
            iam.Policy(
                self,
                "AuditLambdaPermissions",
                statements=[
                    iam.PolicyStatement(
                        actions=["s3:GetObject", "s3:PutObject"],
                        resources=[
                            self.bucket.arn_for_objects(f"{self._raw_prefix}*"),
                            self.bucket.arn_for_objects(f"{self._report_prefix}*"),
                        ],
                    ),
                    iam.PolicyStatement(
                        actions=["secretsmanager:GetSecretValue"],
                        resources=[secret.secret_arn for secret in self.secrets.values()],
                    ),
                    iam.PolicyStatement(
                        actions=[
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                        ],
                        resources=["*"],
                    ),
                ],
            )
        )

        self.step_functions_role = iam.Role(
            self,
            "AuditStateMachineRole",
            assumed_by=iam.ServicePrincipal("states.amazonaws.com"),
            description="Scaffold role for future Step Functions orchestration",
        )

        lambda_env = {
            "BUCKET_NAME": self.bucket.bucket_name,
            "REPORT_PREFIX": self._report_prefix,
            "SECRET_NAMES": json.dumps({k: v.secret_name for k, v in self.secrets.items()}),
            "LOG_LEVEL": log_level,
        }
        if fix_version:
            lambda_env["FIX_VERSION"] = fix_version

        dist_dir = Path(__file__).resolve().parents[2] / "dist" / "lambda"

        self.audit_lambda = _lambda.Function(
            self,
            "AuditLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler=f"{lambda_module}.handler",
            code=_lambda.Code.from_asset(str(dist_dir)),
            timeout=Duration.minutes(15),
            memory_size=1024,
            role=self.lambda_role,
            environment=lambda_env,
        )

        self.schedule = None
        if enable_schedule:
            self.schedule = events.Rule(
                self,
                "DailyAuditSchedule",
                schedule=events.Schedule.expression(schedule_expression),
            )
            self.schedule.add_target(targets.LambdaFunction(self.audit_lambda))

        CfnOutput(self, "BucketName", value=self.bucket.bucket_name)
        CfnOutput(self, "AuditLambdaName", value=self.audit_lambda.function_name)
        CfnOutput(self, "AuditLambdaArn", value=self.audit_lambda.function_arn)
        if self.schedule is not None:
            CfnOutput(self, "DailyRuleName", value=self.schedule.rule_name)

    @staticmethod
    def _normalise_prefix(prefix: str) -> str:
        cleaned = prefix.strip()
        if not cleaned:
            return ""
        if not cleaned.endswith("/"):
            cleaned = f"{cleaned}/"
        return cleaned

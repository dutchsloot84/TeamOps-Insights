"""CDK stack defining the Release Copilot core infrastructure."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_logs as logs,
    aws_s3 as s3,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct


class CoreStack(Stack):
    """Provision the Release Copilot storage, secrets, and execution runtime."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        bucket_name: str,
        jira_secret_arn: Optional[str] = None,
        bitbucket_secret_arn: Optional[str] = None,
        lambda_asset_path: str = "../../dist",
        lambda_handler: str = "main.handler",
        rc_s3_prefix: str = "releasecopilot",
        lambda_timeout_sec: int = 180,
        lambda_memory_mb: int = 512,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        asset_path = Path(lambda_asset_path).expanduser().resolve()
        normalized_prefix = self._normalize_prefix(rc_s3_prefix)

        self.bucket = s3.Bucket(
            self,
            "ArtifactsBucket",
            bucket_name=bucket_name,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            versioned=True,
        )

        self.bucket.add_lifecycle_rule(
            id="RawLifecycle",
            prefix="raw/",
            transitions=[
                s3.Transition(
                    storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                    transition_after=Duration.days(30),
                )
            ],
            expiration=Duration.days(90),
        )

        self.bucket.add_lifecycle_rule(
            id="ReportsLifecycle",
            prefix="reports/",
            transitions=[
                s3.Transition(
                    storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                    transition_after=Duration.days(60),
                )
            ],
        )

        self.jira_secret = self._resolve_secret(
            "JiraSecret",
            provided_arn=jira_secret_arn,
            description="Placeholder Jira OAuth secret for Release Copilot",
        )
        self.bitbucket_secret = self._resolve_secret(
            "BitbucketSecret",
            provided_arn=bitbucket_secret_arn,
            description="Placeholder Bitbucket OAuth secret for Release Copilot",
        )
        secret_arns = [
            self.jira_secret.secret_arn,
            self.bitbucket_secret.secret_arn,
        ]

        self.execution_role = iam.Role(
            self,
            "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Least-privilege execution role for Release Copilot Lambda",
        )

        iam.Policy(
            self,
            "LambdaExecutionPolicy",
            statements=[
                iam.PolicyStatement(
                    actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                    resources=["*"],
                ),
                iam.PolicyStatement(
                    actions=["s3:ListBucket"],
                    resources=[self.bucket.bucket_arn],
                    conditions={"StringLike": {"s3:prefix": [f"{normalized_prefix}/"]}},
                ),
                iam.PolicyStatement(
                    actions=["s3:GetObject", "s3:PutObject"],
                    resources=[self.bucket.arn_for_objects(f"{normalized_prefix}/*")],
                ),
                iam.PolicyStatement(
                    actions=["secretsmanager:GetSecretValue"],
                    resources=secret_arns,
                ),
            ],
        ).attach_to_role(self.execution_role)

        environment = {
            "RC_S3_BUCKET": self.bucket.bucket_name,
            "RC_S3_PREFIX": normalized_prefix,
            "RC_USE_AWS_SECRETS_MANAGER": "true",
        }

        self.lambda_function = _lambda.Function(
            self,
            "ReleaseCopilotLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler=lambda_handler,
            code=_lambda.Code.from_asset(str(asset_path)),
            timeout=Duration.seconds(lambda_timeout_sec),
            memory_size=lambda_memory_mb,
            role=self.execution_role,
            environment=environment,
            log_retention=logs.RetentionDays.ONE_MONTH,
        )

        # EventBridge schedule wiring could be added later using context flags
        CfnOutput(self, "ArtifactsBucketName", value=self.bucket.bucket_name)
        CfnOutput(self, "LambdaName", value=self.lambda_function.function_name)
        CfnOutput(self, "LambdaArn", value=self.lambda_function.function_arn)

    @staticmethod
    def _normalize_prefix(prefix: str) -> str:
        stripped = prefix.strip()
        if not stripped:
            return "releasecopilot"
        return stripped.strip("/")

    def _resolve_secret(
        self,
        construct_id: str,
        *,
        provided_arn: Optional[str],
        description: str,
    ) -> secretsmanager.ISecret:
        if provided_arn:
            return secretsmanager.Secret.from_secret_complete_arn(
                self, construct_id, provided_arn
            )
        return secretsmanager.Secret(
            self,
            construct_id,
            description=description,
            generate_secret_string=secretsmanager.SecretStringGenerator(
                exclude_punctuation=True
            ),
        )

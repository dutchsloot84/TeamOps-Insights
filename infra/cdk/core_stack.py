"""CDK stack defining the ReleaseCopilot core infrastructure."""
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
    """Provision the ReleaseCopilot storage, secrets, and execution runtime."""

    RC_S3_PREFIX = "releasecopilot"

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
        lambda_timeout_sec: int = 180,
        lambda_memory_mb: int = 512,
        schedule_enabled: bool = False,
        schedule_cron: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        asset_path = Path(lambda_asset_path).expanduser().resolve()

        self.bucket = s3.Bucket(
            self,
            "ArtifactsBucket",
            bucket_name=bucket_name,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            versioned=True,
        )

        self.bucket.add_lifecycle_rule(
            id="RawArtifactsLifecycle",
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
            description="Placeholder Jira OAuth secret for ReleaseCopilot",
        )
        self.bitbucket_secret = self._resolve_secret(
            "BitbucketSecret",
            provided_arn=bitbucket_secret_arn,
            description="Placeholder Bitbucket OAuth secret for ReleaseCopilot",
        )

        self.execution_role = iam.Role(
            self,
            "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Least-privilege execution role for ReleaseCopilot Lambda",
        )

        self._attach_policies()

        environment = {
            "RC_S3_BUCKET": self.bucket.bucket_name,
            "RC_S3_PREFIX": self.RC_S3_PREFIX,
            "RC_USE_AWS_SECRETS_MANAGER": "true",
        }

        clamped_timeout = max(180, min(lambda_timeout_sec, 300))
        clamped_memory = max(512, min(lambda_memory_mb, 1024))

        self.lambda_function = _lambda.Function(
            self,
            "ReleaseCopilotLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler=lambda_handler,
            code=_lambda.Code.from_asset(str(asset_path)),
            timeout=Duration.seconds(clamped_timeout),
            memory_size=clamped_memory,
            role=self.execution_role,
            environment=environment,
            log_retention=logs.RetentionDays.ONE_MONTH,
        )

        # EventBridge schedule integration can be added in the future if required.
        CfnOutput(self, "ArtifactsBucketName", value=self.bucket.bucket_name)
        CfnOutput(self, "LambdaName", value=self.lambda_function.function_name)
        CfnOutput(self, "LambdaArn", value=self.lambda_function.function_arn)

    def _attach_policies(self) -> None:
        prefix_objects_arn = self.bucket.arn_for_objects(f"{self.RC_S3_PREFIX}/*")
        log_group_arn = f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/*"

        iam.Policy(
            self,
            "LambdaExecutionPolicy",
            statements=[
                iam.PolicyStatement(
                    sid="AllowS3ObjectAccess",
                    actions=["s3:GetObject", "s3:PutObject"],
                    resources=[prefix_objects_arn],
                ),
                iam.PolicyStatement(
                    sid="AllowS3ListArtifactsPrefix",
                    actions=["s3:ListBucket"],
                    resources=[self.bucket.bucket_arn],
                    conditions={
                        "StringLike": {
                            "s3:prefix": [
                                f"{self.RC_S3_PREFIX}/",
                                f"{self.RC_S3_PREFIX}/*",
                            ]
                        }
                    },
                ),
                iam.PolicyStatement(
                    sid="AllowSecretRetrieval",
                    actions=["secretsmanager:GetSecretValue"],
                    resources=[
                        self.jira_secret.secret_arn,
                        self.bitbucket_secret.secret_arn,
                    ],
                ),
                iam.PolicyStatement(
                    sid="AllowLambdaLogging",
                    actions=[
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                    ],
                    resources=[log_group_arn],
                ),
            ],
        ).attach_to_role(self.execution_role)

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
                exclude_punctuation=True,
            ),
        )

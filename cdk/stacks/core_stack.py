"""Core AWS infrastructure for ReleaseCopilot."""
from __future__ import annotations

from aws_cdk import (
    CfnOutput,
    RemovalPolicy,
    Stack,
    aws_iam as iam,
    aws_s3 as s3,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct


class CoreStack(Stack):
    """Provision foundational resources shared by compute workloads."""

    def __init__(self, scope: Construct, construct_id: str, *, project_name: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.artifacts_bucket = s3.Bucket(
            self,
            "ArtifactsBucket",
            bucket_name=None,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        self.oauth_secret = secretsmanager.Secret(
            self,
            "OauthSecret",
            description="releasecopilot-ai OAuth (Jira/Bitbucket)",
            secret_name=f"{project_name}/oauth",
        )

        self.exec_policy = iam.ManagedPolicy(
            self,
            "AuditExecutionPolicy",
            statements=[
                iam.PolicyStatement(
                    actions=["secretsmanager:GetSecretValue"],
                    resources=[self.oauth_secret.secret_arn],
                ),
                iam.PolicyStatement(
                    actions=[
                        "s3:AbortMultipartUpload",
                        "s3:GetBucketLocation",
                        "s3:ListBucket",
                        "s3:PutObject",
                        "s3:PutObjectAcl",
                    ],
                    resources=[
                        self.artifacts_bucket.bucket_arn,
                        f"{self.artifacts_bucket.bucket_arn}/*",
                    ],
                ),
                iam.PolicyStatement(
                    actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                    resources=["*"],
                ),
            ],
        )

        self.lambda_role = iam.Role(
            self,
            "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                self.exec_policy,
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ],
        )

        self.ecs_task_role = iam.Role(
            self,
            "EcsTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[self.exec_policy],
        )

        CfnOutput(self, "ArtifactsBucketName", value=self.artifacts_bucket.bucket_name)
        CfnOutput(self, "OauthSecretArn", value=self.oauth_secret.secret_arn)
        CfnOutput(self, "LambdaRoleArn", value=self.lambda_role.role_arn)
        CfnOutput(self, "EcsTaskRoleArn", value=self.ecs_task_role.role_arn)

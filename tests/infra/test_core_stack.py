"""Unit tests validating the CDK core stack resources."""
from __future__ import annotations

from pathlib import Path

from aws_cdk import App, Environment
from aws_cdk.assertions import Match, Template

from infra.cdk.core_stack import CoreStack


ACCOUNT = "123456789012"
REGION = "us-west-2"
ASSET_DIR = str(Path(__file__).resolve().parents[2] / "dist")


def _synth_template(**overrides) -> Template:
    app = App()
    stack = CoreStack(
        app,
        "TestCoreStack",
        env=Environment(account=ACCOUNT, region=REGION),
        bucket_name=f"releasecopilot-artifacts-{ACCOUNT}",
        lambda_asset_path=ASSET_DIR,
        **overrides,
    )
    return Template.from_stack(stack)


def test_bucket_encryption_and_versioning() -> None:
    template = _synth_template()
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "VersioningConfiguration": {"Status": "Enabled"},
            "BucketEncryption": {
                "ServerSideEncryptionConfiguration": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "ServerSideEncryptionByDefault": {
                                    "SSEAlgorithm": "AES256"
                                }
                            }
                        )
                    ]
                )
            },
        },
    )


def test_bucket_lifecycle_rules() -> None:
    template = _synth_template()
    bucket = next(iter(template.find_resources("AWS::S3::Bucket").values()))
    lifecycle_rules = bucket["Properties"]["LifecycleConfiguration"]["Rules"]

    raw_rule = next(rule for rule in lifecycle_rules if rule["Prefix"] == "raw/")
    assert raw_rule["ExpirationInDays"] == 90
    assert raw_rule["Transitions"] == [
        {"StorageClass": "STANDARD_IA", "TransitionInDays": 30}
    ]

    reports_rule = next(rule for rule in lifecycle_rules if rule["Prefix"] == "reports/")
    assert "ExpirationInDays" not in reports_rule
    assert reports_rule["Transitions"] == [
        {"StorageClass": "STANDARD_IA", "TransitionInDays": 60}
    ]


def test_iam_policy_statements() -> None:
    template = _synth_template()
    policy = next(iter(template.find_resources("AWS::IAM::Policy").values()))
    statements = policy["Properties"]["PolicyDocument"]["Statement"]

    assert {stmt["Sid"] for stmt in statements} == {
        "AllowS3ObjectAccess",
        "AllowS3ListArtifactsPrefix",
        "AllowSecretRetrieval",
        "AllowLambdaLogging",
    }

    object_statement = next(stmt for stmt in statements if stmt["Sid"] == "AllowS3ObjectAccess")
    assert set(object_statement["Action"]) == {"s3:GetObject", "s3:PutObject"}
    object_resource = object_statement["Resource"]
    assert object_resource["Fn::Join"][1][1] == "/releasecopilot/*"

    list_statement = next(stmt for stmt in statements if stmt["Sid"] == "AllowS3ListArtifactsPrefix")
    assert list_statement["Action"] == "s3:ListBucket"
    assert list_statement["Condition"] == {
        "StringLike": {"s3:prefix": ["releasecopilot/", "releasecopilot/*"]}
    }

    secrets_statement = next(stmt for stmt in statements if stmt["Sid"] == "AllowSecretRetrieval")
    assert secrets_statement["Action"] == "secretsmanager:GetSecretValue"
    assert len(secrets_statement["Resource"]) == 2

    logs_statement = next(stmt for stmt in statements if stmt["Sid"] == "AllowLambdaLogging")
    assert set(logs_statement["Action"]) == {
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
    }
    assert logs_statement["Resource"].endswith(":log-group:/aws/lambda/*")


def test_lambda_environment_and_log_retention() -> None:
    template = _synth_template()
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Runtime": "python3.11",
            "Environment": {
                "Variables": Match.object_equals(
                    {
                        "RC_S3_BUCKET": Match.any_value(),
                        "RC_S3_PREFIX": "releasecopilot",
                        "RC_USE_AWS_SECRETS_MANAGER": "true",
                    }
                )
            },
        },
    )

    template.has_resource_properties(
        "Custom::LogRetention",
        {"RetentionInDays": 30},
    )


def test_stack_outputs_present() -> None:
    template = _synth_template()
    outputs = template.to_json()["Outputs"]
    assert "ArtifactsBucketName" in outputs
    assert "LambdaArn" in outputs

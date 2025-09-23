"""Unit tests validating the CDK core stack resources."""
from __future__ import annotations

from aws_cdk import App
from aws_cdk.assertions import Match, Template

from infra.cdk.core_stack import CoreStack


JIRA_ARN = "arn:aws:secretsmanager:us-west-2:111111111111:secret:/releasecopilot/jira-ABC123"
BITBUCKET_ARN = "arn:aws:secretsmanager:us-west-2:111111111111:secret:/releasecopilot/bitbucket-DEF456"


def _synth_template() -> Template:
    app = App()
    stack = CoreStack(
        app,
        "TestCoreStack",
        bucket_name="releasecopilot-artifacts-111111111111",
        jira_secret_arn=JIRA_ARN,
        bitbucket_secret_arn=BITBUCKET_ARN,
        lambda_asset_path="dist",
        rc_s3_prefix="releasecopilot",
    )
    return Template.from_stack(stack)


def test_bucket_encryption_and_versioning() -> None:
    template = _synth_template()
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "VersioningConfiguration": {"Status": "Enabled"},
            "BucketEncryption": {
                "ServerSideEncryptionConfiguration": Match.array_with([
                    Match.object_like({"ServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}})
                ])
            },
        },
    )


def test_bucket_lifecycle_rules() -> None:
    template = _synth_template()
    buckets = template.find_resources("AWS::S3::Bucket")
    assert len(buckets) == 1
    bucket_props = next(iter(buckets.values()))["Properties"]
    lifecycle_rules = bucket_props["LifecycleConfiguration"]["Rules"]

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
    policies = template.find_resources("AWS::IAM::Policy")
    policy = next(
        props
        for props in policies.values()
        if props["Properties"]["PolicyName"].startswith("LambdaExecutionPolicy")
    )

    statements = policy["Properties"]["PolicyDocument"]["Statement"]

    logs_statement = next(
        stmt
        for stmt in statements
        if isinstance(stmt.get("Action"), list)
        and set(stmt["Action"]) == {
            "logs:CreateLogGroup",
            "logs:CreateLogStream",
            "logs:PutLogEvents",
        }
    )
    assert logs_statement["Resource"] == "*"

    list_statement = next(
        stmt for stmt in statements if stmt.get("Action") == "s3:ListBucket"
    )
    assert list_statement["Condition"] == {"StringLike": {"s3:prefix": ["releasecopilot/"]}}
    list_resource = list_statement["Resource"]
    assert list_resource["Fn::GetAtt"][1] == "Arn"

    object_statement = next(
        stmt
        for stmt in statements
        if isinstance(stmt.get("Action"), list)
        and set(stmt["Action"]) == {"s3:GetObject", "s3:PutObject"}
    )
    join_parts = object_statement["Resource"]["Fn::Join"][1]
    bucket_part = join_parts[0]
    assert bucket_part["Fn::GetAtt"][1] == "Arn"
    assert join_parts[1] == "/releasecopilot/*"

    secrets_statement = next(
        stmt
        for stmt in statements
        if stmt.get("Action") == "secretsmanager:GetSecretValue"
    )
    assert secrets_statement["Resource"] == [JIRA_ARN, BITBUCKET_ARN]


def test_lambda_environment_and_log_retention() -> None:
    template = _synth_template()
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Handler": "main.handler",
            "Environment": {
                "Variables": Match.object_like(
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

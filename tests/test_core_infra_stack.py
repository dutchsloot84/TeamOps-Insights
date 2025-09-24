from __future__ import annotations

from pathlib import Path

from aws_cdk import App, Environment
from aws_cdk.assertions import Match, Template

from infra.cdk.core_stack import CoreStack


ACCOUNT = "123456789012"
REGION = "us-west-2"
ASSET_DIR = str(Path(__file__).resolve().parents[1] / "dist")


def _synth_stack(**overrides) -> Template:
    app = App()
    stack = CoreStack(
        app,
        "TestCore",
        env=Environment(account=ACCOUNT, region=REGION),
        bucket_name=f"releasecopilot-artifacts-{ACCOUNT}",
        lambda_asset_path=ASSET_DIR,
        **overrides,
    )
    return Template.from_stack(stack)


def test_bucket_configured_with_security_controls() -> None:
    template = _synth_stack()

    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "VersioningConfiguration": {"Status": "Enabled"},
            "BucketEncryption": {
                "ServerSideEncryptionConfiguration": [
                    {
                        "ServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}
                    }
                ]
            },
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            },
        },
    )


def test_lambda_has_expected_configuration() -> None:
    template = _synth_stack(lambda_handler="main.handler", lambda_timeout_sec=240, lambda_memory_mb=800)

    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Handler": "main.handler",
            "Runtime": "python3.11",
            "Timeout": 240,
            "MemorySize": 800,
            "Environment": {
                "Variables": Match.object_like(
                    {
                        "RC_S3_BUCKET": Match.any_value(),
                        "RC_S3_PREFIX": "releasecopilot",
                        "RC_USE_AWS_SECRETS_MANAGER": "true",
                        "JIRA_TABLE_NAME": Match.any_value(),
                    }
                )
            },
        },
    )


def test_webhook_lambda_and_api_created() -> None:
    template = _synth_stack()

    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "PointInTimeRecoverySpecification": {"PointInTimeRecoveryEnabled": True},
            "BillingMode": "PAY_PER_REQUEST",
            "KeySchema": [
                {"AttributeName": "issue_id", "KeyType": "HASH"},
            ],
            "AttributeDefinitions": Match.array_with(
                [
                    Match.object_like({"AttributeName": "issue_id"}),
                    Match.object_like({"AttributeName": "fix_version"}),
                    Match.object_like({"AttributeName": "status"}),
                    Match.object_like({"AttributeName": "assignee"}),
                ]
            ),
            "GlobalSecondaryIndexes": Match.array_with(
                [
                    Match.object_like({"IndexName": "FixVersionIndex"}),
                    Match.object_like({"IndexName": "StatusIndex"}),
                    Match.object_like({"IndexName": "AssigneeIndex"}),
                ]
            ),
            "SSESpecification": {"SSEEnabled": True},
        },
    )

    template.has_resource_properties(
        "AWS::Lambda::Function",
        Match.object_like(
            {
                "Handler": "handler.handler",
                "Runtime": "python3.11",
                "Environment": {
                    "Variables": Match.object_like({"TABLE_NAME": Match.any_value()}),
                },
            }
        ),
    )

    template.has_resource_properties(
        "AWS::ApiGateway::RestApi",
        {"Name": "ReleaseCopilotJiraWebhook"},
    )


def test_eventbridge_rule_targets_lambda_when_enabled() -> None:
    template = _synth_stack(schedule_enabled=True, schedule_cron="cron(30 8 * * ? *)")

    rules = template.find_resources("AWS::Events::Rule")
    assert len(rules) == 1

    rule = next(iter(rules.values()))
    properties = rule["Properties"]

    assert properties["ScheduleExpression"] == "cron(30 8 * * ? *)"
    assert properties["State"] == "ENABLED"

    targets = properties["Targets"]
    assert len(targets) == 1

    target = targets[0]
    assert target["Id"] == "Target0"

    arn_getatt = target["Arn"]["Fn::GetAtt"]
    assert arn_getatt[1] == "Arn"
    assert arn_getatt[0].startswith("ReleaseCopilotLambda")


def test_eventbridge_rule_not_created_when_disabled() -> None:
    template = _synth_stack(schedule_enabled=False)

    assert template.find_resources("AWS::Events::Rule") == {}

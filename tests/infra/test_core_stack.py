"""Unit tests validating the CDK core stack resources."""
from __future__ import annotations

from pathlib import Path

import pytest
from aws_cdk import App, Environment
from aws_cdk.assertions import Match, Template

from infra.cdk.core_stack import CoreStack


ACCOUNT = "123456789012"
REGION = "us-west-2"
ASSET_DIR = str(Path(__file__).resolve().parents[2] / "dist")


def _synth_template(*, app_context: dict[str, str] | None = None, **overrides) -> Template:
    app = App(context=app_context or {})
    stack = CoreStack(
        app,
        "TestCoreStack",
        env=Environment(account=ACCOUNT, region=REGION),
        bucket_name=f"releasecopilot-artifacts-{ACCOUNT}",
        lambda_asset_path=ASSET_DIR,
        **overrides,
    )
    return Template.from_stack(stack)


def _create_stack(*, app_context: dict[str, str] | None = None, **overrides) -> CoreStack:
    app = App(context=app_context or {})
    return CoreStack(
        app,
        "TestCoreStack",
        env=Environment(account=ACCOUNT, region=REGION),
        bucket_name=f"releasecopilot-artifacts-{ACCOUNT}",
        lambda_asset_path=ASSET_DIR,
        **overrides,
    )


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
    policies = template.find_resources("AWS::IAM::Policy")
    policy = next(
        policy
        for name, policy in policies.items()
        if "LambdaExecutionPolicy" in name
    )
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


def test_lambda_environment_and_log_groups() -> None:
    template = _synth_template()
    template.has_resource_properties(
        "AWS::Lambda::Function",
        Match.object_like(
            {
            "Runtime": "python3.11",
            "Environment": {
                "Variables": Match.object_like(
                    {
                        "RC_S3_BUCKET": Match.any_value(),
                        "RC_S3_PREFIX": "releasecopilot",
                        "RC_USE_AWS_SECRETS_MANAGER": "true",
                    }
                )
            },
        }
        ),
    )

    log_groups = template.find_resources("AWS::Logs::LogGroup")
    assert len(log_groups) >= 3
    for log_group in log_groups.values():
        assert log_group["Properties"].get("RetentionInDays") == 30

    assert not template.find_resources("Custom::LogRetention")


def test_lambda_asset_paths_are_stable() -> None:
    project_root = Path(__file__).resolve().parents[2]
    webhook_path = project_root / "services" / "jira_sync_webhook"
    reconciliation_path = project_root / "services" / "jira_reconciliation_job"

    assert webhook_path.is_dir()
    assert reconciliation_path.is_dir()


def test_stack_raises_when_asset_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = Path(__file__).resolve().parents[2]
    webhook_path = project_root / "services" / "jira_sync_webhook"
    reconciliation_path = project_root / "services" / "jira_reconciliation_job"

    original_exists = Path.exists

    def fake_exists(self: Path) -> bool:
        if self in {webhook_path, reconciliation_path}:
            return False
        return original_exists(self)

    monkeypatch.setattr(Path, "exists", fake_exists)

    with pytest.raises(FileNotFoundError):
        _create_stack()


def test_lambda_alarms_created() -> None:
    template = _synth_template()
    template.resource_count_is("AWS::CloudWatch::Alarm", 2)


def test_sns_topic_created_when_alarm_email_provided() -> None:
    template = _synth_template(app_context={"alarmEmail": "ops@example.com"})
    template.resource_count_is("AWS::SNS::Topic", 1)
    template.resource_count_is("AWS::SNS::Subscription", 1)
    template.has_resource_properties(
        "AWS::SNS::Subscription",
        {"Endpoint": "ops@example.com"},
    )


def test_stack_outputs_present() -> None:
    template = _synth_template()
    outputs = template.to_json()["Outputs"]
    assert "ArtifactsBucketName" in outputs
    assert "LambdaArn" in outputs
    assert "JiraReconciliationLambdaName" in outputs


def test_eventbridge_rule_targets_lambda_when_enabled() -> None:
    template = _synth_template(
        schedule_enabled=True,
        schedule_cron="cron(0 12 * * ? *)",
    )

    rules = template.find_resources("AWS::Events::Rule")
    assert len(rules) == 2

    release_rule = next(
        rule
        for rule in rules.values()
        if rule["Properties"]["Targets"][0]["Arn"]["Fn::GetAtt"][0].startswith("ReleaseCopilotLambda")
    )
    release_properties = release_rule["Properties"]
    assert release_properties["ScheduleExpression"] == "cron(0 12 * * ? *)"

    reconciliation_rule = next(
        rule
        for rule in rules.values()
        if rule["Properties"]["Targets"][0]["Arn"]["Fn::GetAtt"][0].startswith("JiraReconciliationLambda")
    )
    reconciliation_properties = reconciliation_rule["Properties"]
    assert reconciliation_properties["ScheduleExpression"] == "cron(15 7 * * ? *)"
    assert reconciliation_properties["Targets"][0]["DeadLetterConfig"]


def test_eventbridge_rule_absent_when_schedule_disabled() -> None:
    template = _synth_template(schedule_enabled=False)

    rules = template.find_resources("AWS::Events::Rule")
    assert len(rules) == 1
    target = rules[next(iter(rules))]["Properties"]["Targets"][0]
    assert target["Arn"]["Fn::GetAtt"][0].startswith("JiraReconciliationLambda")


def test_reconciliation_lambda_and_queue_created() -> None:
    template = _synth_template()

    template.has_resource_properties(
        "AWS::Lambda::Function",
        Match.object_like(
            {
                "Handler": "handler.handler",
                "Runtime": "python3.11",
                "Environment": {
                    "Variables": Match.object_like(
                        {
                            "JIRA_BASE_URL": Match.any_value(),
                            "JIRA_SECRET_ARN": Match.any_value(),
                            "METRICS_NAMESPACE": "ReleaseCopilot/JiraSync",
                        }
                    )
                },
            }
        ),
    )

    template.has_resource_properties(
        "AWS::SQS::Queue",
        {
            "MessageRetentionPeriod": 1209600,
        },
    )

"""Tests for the core audit CDK stack."""
from __future__ import annotations

from aws_cdk import App
from aws_cdk.assertions import Match, Template

from infra.cdk.core_stack import CoreStack


DEFAULT_CONTEXT = {
    "env_name": "dev",
    "bucket_base": "releasecopilot",
    "secret_names": {"jira": "rc/jira", "bitbucket": "rc/bitbucket"},
}


def _synth_stack(**overrides):
    app = App()
    params = {**DEFAULT_CONTEXT, **overrides}
    stack = CoreStack(app, "TestCore", **params)
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
                        "ServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "AES256"
                        }
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
    template = _synth_stack()

    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Handler": "aws.core_handler.handler",
            "Runtime": "python3.11",
            "Timeout": 900,
            "Environment": {
                "Variables": Match.object_like(
                    {
                        "BUCKET_NAME": Match.any_value(),
                        "REPORT_PREFIX": "reports/",
                        "SECRET_NAMES": Match.any_value(),
                        "LOG_LEVEL": "INFO",
                    }
                )
            },
        },
    )

    template.has_resource_properties(
        "AWS::IAM::Policy",
        Match.object_like(
            {
                "PolicyDocument": {
                    "Statement": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "Action": ["s3:GetObject", "s3:PutObject"],
                                    "Resource": Match.array_with(
                                        [
                                            Match.object_like(
                                                {
                                                    "Fn::Join": Match.array_with(
                                                        [
                                                            "",
                                                            Match.array_with(
                                                                [
                                                                    Match.object_like(
                                                                        {
                                                                            "Fn::GetAtt": Match.array_with(
                                                                                [
                                                                                    Match.string_like_regexp(
                                                                                        "AuditArtifactsBucket"
                                                                                    ),
                                                                                    "Arn",
                                                                                ]
                                                                            )
                                                                        }
                                                                    ),
                                                                    "/raw/*",
                                                                ]
                                                            ),
                                                        ]
                                                    )
                                                }
                                            ),
                                            Match.object_like(
                                                {
                                                    "Fn::Join": Match.array_with(
                                                        [
                                                            "",
                                                            Match.array_with(
                                                                [
                                                                    Match.object_like(
                                                                        {
                                                                            "Fn::GetAtt": Match.array_with(
                                                                                [
                                                                                    Match.string_like_regexp(
                                                                                        "AuditArtifactsBucket"
                                                                                    ),
                                                                                    "Arn",
                                                                                ]
                                                                            )
                                                                        }
                                                                    ),
                                                                    "/reports/*",
                                                                ]
                                                            ),
                                                        ]
                                                    )
                                                }
                                            ),
                                        ]
                                    ),
                                }
                            ),
                            Match.object_like(
                                {
                                    "Action": "secretsmanager:GetSecretValue",
                                    "Resource": Match.array_with(
                                        [
                                            Match.object_like(
                                                {
                                                    "Ref": Match.string_like_regexp("JiraSecret"),
                                                }
                                            ),
                                            Match.object_like(
                                                {
                                                    "Ref": Match.string_like_regexp("BitbucketSecret"),
                                                }
                                            ),
                                        ]
                                    ),
                                }
                            ),
                        ]
                    )
                }
            }
        ),
    )


def test_eventbridge_rule_targets_lambda_when_enabled() -> None:
    template = _synth_stack(enable_schedule=True)

    template.has_resource_properties(
        "AWS::Events::Rule",
        {
            "ScheduleExpression": "cron(30 8 * * ? *)",
            "State": "ENABLED",
            "Targets": [
                Match.object_like(
                    {
                        "Arn": {"Fn::GetAtt": [Match.string_like_regexp("AuditLambda"), "Arn"]},
                    }
                )
            ],
        },
    )

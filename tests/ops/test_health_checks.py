"""Unit tests for readiness health checks."""
from __future__ import annotations

import json
from contextlib import ExitStack

import boto3
import pytest
from botocore.stub import ANY, Stubber

from src.ops.health import ReadinessClients, ReadinessOptions, run_readiness


@pytest.fixture(autouse=True)
def _aws_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")


def _clients(region: str = "us-east-1") -> ReadinessClients:
    return ReadinessClients(
        secrets=boto3.client("secretsmanager", region_name=region),
        dynamodb=boto3.client("dynamodb", region_name=region),
        s3=boto3.client("s3", region_name=region),
    )


def test_run_readiness_success() -> None:
    clients = _clients()
    options = ReadinessOptions(
        region="us-east-1",
        bucket="releasecopilot-artifacts",
        prefix="reports",
        table_name="releasecopilot-jira",
        secrets={"jira": "secret/jira"},
        webhook_secret_id="secret/webhook",
        webhook_env_present=False,
        clients=clients,
    )

    with ExitStack() as stack:
        secrets_stub = stack.enter_context(Stubber(clients.secrets))
        ddb_stub = stack.enter_context(Stubber(clients.dynamodb))
        s3_stub = stack.enter_context(Stubber(clients.s3))

        secrets_stub.add_response(
            "get_secret_value",
            {"SecretString": json.dumps({"token": "value"})},
            {"SecretId": "secret/jira"},
        )
        secrets_stub.add_response(
            "get_secret_value",
            {"SecretString": "webhook"},
            {"SecretId": "secret/webhook"},
        )

        ddb_stub.add_response(
            "describe_table",
            {
                "Table": {
                    "TableName": options.table_name,
                    "KeySchema": [{"AttributeName": "issue_id", "KeyType": "HASH"}],
                    "AttributeDefinitions": [{"AttributeName": "issue_id", "AttributeType": "S"}],
                }
            },
            {"TableName": options.table_name},
        )
        ddb_stub.add_response(
            "put_item",
            {},
            {"TableName": options.table_name, "Item": {"issue_id": {"S": ANY}}},
        )
        ddb_stub.add_response(
            "delete_item",
            {},
            {"TableName": options.table_name, "Key": {"issue_id": {"S": ANY}}},
        )

        s3_stub.add_response(
            "put_object",
            {},
            {
                "Bucket": options.bucket,
                "Key": ANY,
                "Body": b"releasecopilot-readiness",
                "ServerSideEncryption": "AES256",
            },
        )
        s3_stub.add_response(
            "delete_object",
            {},
            {"Bucket": options.bucket, "Key": ANY},
        )

        report = run_readiness(options)

    assert report.is_success()
    assert report.cleanup_warning is None
    assert report.checks["secrets"]["status"] == "pass"
    assert report.checks["dynamodb"]["status"] == "pass"
    assert report.checks["s3"]["status"] == "pass"
    assert report.checks["webhook_secret"]["status"] == "pass"


def test_readiness_reports_secret_failure() -> None:
    clients = _clients()
    options = ReadinessOptions(
        region="us-east-1",
        bucket="bucket",
        prefix=None,
        table_name="table",
        secrets={"jira": "secret/missing"},
        webhook_secret_id="secret/webhook",
        webhook_env_present=True,
        clients=clients,
    )

    with ExitStack() as stack:
        secrets_stub = stack.enter_context(Stubber(clients.secrets))
        ddb_stub = stack.enter_context(Stubber(clients.dynamodb))
        s3_stub = stack.enter_context(Stubber(clients.s3))

        secrets_stub.add_client_error(
            "get_secret_value",
            service_error_code="ResourceNotFoundException",
            expected_params={"SecretId": "secret/missing"},
        )

        ddb_stub.add_response(
            "describe_table",
            {
                "Table": {
                    "TableName": options.table_name,
                    "KeySchema": [{"AttributeName": "pk", "KeyType": "HASH"}],
                    "AttributeDefinitions": [{"AttributeName": "pk", "AttributeType": "S"}],
                }
            },
            {"TableName": options.table_name},
        )
        ddb_stub.add_response(
            "put_item",
            {},
            {"TableName": options.table_name, "Item": {"pk": {"S": ANY}}},
        )
        ddb_stub.add_response(
            "delete_item",
            {},
            {"TableName": options.table_name, "Key": {"pk": {"S": ANY}}},
        )

        s3_stub.add_response(
            "put_object",
            {},
            {
                "Bucket": options.bucket,
                "Key": ANY,
                "Body": b"releasecopilot-readiness",
                "ServerSideEncryption": "AES256",
            },
        )
        s3_stub.add_response(
            "delete_object",
            {},
            {"Bucket": options.bucket, "Key": ANY},
        )

        report = run_readiness(options)

    assert not report.is_success()
    assert report.checks["secrets"]["status"] == "fail"
    assert "unable to read" in report.checks["secrets"].get("reason", "")


def test_webhook_missing_fails() -> None:
    clients = _clients()
    options = ReadinessOptions(
        region="us-east-1",
        bucket="bucket",
        prefix="health",
        table_name="table",
        secrets={},
        webhook_secret_id=None,
        webhook_env_present=False,
        clients=clients,
    )

    with ExitStack() as stack:
        ddb_stub = stack.enter_context(Stubber(clients.dynamodb))
        s3_stub = stack.enter_context(Stubber(clients.s3))

        ddb_stub.add_response(
            "describe_table",
            {
                "Table": {
                    "TableName": options.table_name,
                    "KeySchema": [{"AttributeName": "pk", "KeyType": "HASH"}],
                    "AttributeDefinitions": [{"AttributeName": "pk", "AttributeType": "S"}],
                }
            },
            {"TableName": options.table_name},
        )
        ddb_stub.add_response(
            "put_item",
            {},
            {"TableName": options.table_name, "Item": {"pk": {"S": ANY}}},
        )
        ddb_stub.add_response(
            "delete_item",
            {},
            {"TableName": options.table_name, "Key": {"pk": {"S": ANY}}},
        )

        s3_stub.add_response(
            "put_object",
            {},
            {
                "Bucket": options.bucket,
                "Key": ANY,
                "Body": b"releasecopilot-readiness",
                "ServerSideEncryption": "AES256",
            },
        )
        s3_stub.add_response(
            "delete_object",
            {},
            {"Bucket": options.bucket, "Key": ANY},
        )

        report = run_readiness(options)

    assert not report.is_success()
    assert report.checks["webhook_secret"]["status"] == "fail"
    assert "not configured" in report.checks["webhook_secret"].get("reason", "")


def test_s3_cleanup_warning() -> None:
    clients = _clients()
    options = ReadinessOptions(
        region="us-east-1",
        bucket="bucket",
        prefix=None,
        table_name="table",
        secrets={},
        webhook_secret_id="secret/webhook",
        webhook_env_present=True,
        clients=clients,
    )

    with ExitStack() as stack:
        secrets_stub = stack.enter_context(Stubber(clients.secrets))
        ddb_stub = stack.enter_context(Stubber(clients.dynamodb))
        s3_stub = stack.enter_context(Stubber(clients.s3))

        secrets_stub.add_response(
            "get_secret_value",
            {"SecretString": "token"},
            {"SecretId": "secret/webhook"},
        )

        ddb_stub.add_response(
            "describe_table",
            {
                "Table": {
                    "TableName": options.table_name,
                    "KeySchema": [{"AttributeName": "pk", "KeyType": "HASH"}],
                    "AttributeDefinitions": [{"AttributeName": "pk", "AttributeType": "S"}],
                }
            },
            {"TableName": options.table_name},
        )
        ddb_stub.add_response(
            "put_item",
            {},
            {"TableName": options.table_name, "Item": {"pk": {"S": ANY}}},
        )
        ddb_stub.add_response(
            "delete_item",
            {},
            {"TableName": options.table_name, "Key": {"pk": {"S": ANY}}},
        )

        s3_stub.add_response(
            "put_object",
            {},
            {
                "Bucket": options.bucket,
                "Key": ANY,
                "Body": b"releasecopilot-readiness",
                "ServerSideEncryption": "AES256",
            },
        )
        s3_stub.add_client_error(
            "delete_object",
            service_error_code="AccessDenied",
            expected_params={"Bucket": options.bucket, "Key": ANY},
        )

        report = run_readiness(options)

    assert report.is_success()
    assert report.cleanup_warning is not None
    assert "S3" in report.cleanup_warning


def test_dry_run_skips_aws_calls() -> None:
    clients = _clients()
    options = ReadinessOptions(
        region="us-east-1",
        bucket="bucket",
        prefix="prefix",
        table_name="table",
        secrets={"jira": "secret/jira"},
        webhook_secret_id="secret/webhook",
        webhook_env_present=False,
        dry_run=True,
        clients=clients,
    )

    report = run_readiness(options)

    assert report.is_success()
    assert report.dry_run is True
    for check in report.checks.values():
        assert check["status"] == "pass"

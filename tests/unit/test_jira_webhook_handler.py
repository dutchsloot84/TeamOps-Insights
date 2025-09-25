from __future__ import annotations

import json
import os
import importlib
from typing import Any, Dict, List

import pytest

os.environ.setdefault("TABLE_NAME", "test-table")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
webhook_handler = importlib.import_module("services.jira_sync_webhook.handler")


class DummyTable:
    def __init__(self) -> None:
        self.items: List[Dict[str, Any]] = []
        self.deleted: List[Dict[str, Any]] = []

    def put_item(self, **kwargs: Any) -> None:  # pragma: no cover - exercised in tests
        self.items.append(kwargs)

    def delete_item(self, **kwargs: Any) -> None:  # pragma: no cover - exercised in tests
        self.deleted.append(kwargs)


@pytest.fixture(autouse=True)
def _patch_table(monkeypatch: pytest.MonkeyPatch) -> DummyTable:
    table = DummyTable()
    monkeypatch.setenv("TABLE_NAME", "test-table")
    monkeypatch.delenv("WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("WEBHOOK_SECRET_ARN", raising=False)
    monkeypatch.setitem(webhook_handler.__dict__, "_TABLE", table)
    monkeypatch.setitem(webhook_handler.__dict__, "TABLE_NAME", "test-table")
    monkeypatch.setitem(webhook_handler.__dict__, "_SECRET_CACHE", None)
    monkeypatch.setitem(webhook_handler.__dict__, "_SECRETS", None)
    return table


def _build_event(body: Dict[str, Any], headers: Dict[str, str] | None = None) -> Dict[str, Any]:
    return {
        "httpMethod": "POST",
        "headers": headers or {},
        "body": json.dumps(body),
        "isBase64Encoded": False,
    }


def test_rejects_invalid_method() -> None:
    response = webhook_handler.handler({"httpMethod": "GET"}, None)
    assert response["statusCode"] == 405


def test_upsert_event_persists_issue(monkeypatch: pytest.MonkeyPatch, _patch_table: DummyTable) -> None:
    event = _build_event(
        {
            "webhookEvent": "jira:issue_updated",
            "issue": {
                "id": "1000",
                "key": "ABC-1",
                "fields": {
                    "updated": "2024-05-01T12:00:00.000+0000",
                    "project": {"key": "ABC"},
                    "status": {"name": "In Progress"},
                    "assignee": {"displayName": "Ada"},
                    "fixVersions": [{"name": "2024.05"}],
                },
            },
        }
    )

    monkeypatch.setenv("TABLE_NAME", "test-table")
    response = webhook_handler.handler(event, None)

    assert response["statusCode"] == 202
    assert _patch_table.items
    item = _patch_table.items[0]
    assert item["Item"]["issue_id"] == "1000"
    assert item["Item"]["fix_version"] == "2024.05"


def test_delete_event_removes_issue(monkeypatch: pytest.MonkeyPatch, _patch_table: DummyTable) -> None:
    event = _build_event(
        {
            "webhookEvent": "jira:issue_deleted",
            "issue": {"id": "1000", "key": "ABC-1"},
        }
    )
    response = webhook_handler.handler(event, None)
    assert response["statusCode"] == 202
    assert _patch_table.deleted[0]["Key"] == {"issue_id": "1000"}


def test_rejects_invalid_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBHOOK_SECRET", "expected")
    monkeypatch.setitem(webhook_handler.__dict__, "WEBHOOK_SECRET", "expected")
    event = _build_event({"webhookEvent": "jira:issue_created", "issue": {"id": "1", "key": "A"}})
    response = webhook_handler.handler(event, None)
    assert response["statusCode"] == 401


def test_conditional_failure_is_ignored(monkeypatch: pytest.MonkeyPatch, _patch_table: DummyTable) -> None:
    class FailOnceTable(DummyTable):
        def __init__(self) -> None:
            super().__init__()
            self.called = False

        def put_item(self, **kwargs: Any) -> None:  # pragma: no cover - exercised in tests
            if not self.called:
                self.called = True
                from botocore.exceptions import ClientError

                raise ClientError(
                    error_response={"Error": {"Code": "ConditionalCheckFailedException"}},
                    operation_name="PutItem",
                )
            super().put_item(**kwargs)

    table = FailOnceTable()
    monkeypatch.setitem(webhook_handler.__dict__, "_TABLE", table)

    event = _build_event(
        {
            "webhookEvent": "jira:issue_updated",
            "issue": {"id": "1", "key": "A", "fields": {"updated": "2024-05-01T00:00:00.000+0000"}},
        }
    )
    response = webhook_handler.handler(event, None)
    assert response["statusCode"] == 202


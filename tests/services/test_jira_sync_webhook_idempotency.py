from __future__ import annotations

import importlib
import sys
from typing import Any, Dict

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("TABLE_NAME", "jira-webhook-test")
    yield


def _reload() -> Any:
    module = "services.jira_sync_webhook.handler"
    if module in sys.modules:
        importlib.reload(sys.modules[module])
    else:
        importlib.import_module(module)
    return importlib.import_module(module)


def _payload(updated: str = "2024-01-01T00:00:00.000+0000", delivery: str = "delivery-1") -> Dict[str, Any]:
    return {
        "webhookEvent": "jira:issue_updated",
        "deliveryId": delivery,
        "issue": {
            "id": "1000",
            "key": "MOB-1",
            "fields": {
                "updated": updated,
                "project": {"key": "MOB"},
                "status": {"name": "In Progress"},
                "assignee": {"displayName": "Jane"},
                "fixVersions": [{"name": "1.0"}],
            },
        },
    }


def test_upsert_persists_idempotency_key(monkeypatch: pytest.MonkeyPatch) -> None:
    handler = _reload()
    captured: Dict[str, Any] = {}

    def _capture(item: Dict[str, Any]) -> None:
        captured.update(item)

    monkeypatch.setattr(handler, "_put_item_with_retry", _capture)

    handler._handle_upsert(_payload())

    assert captured["issue_key"] == "MOB-1"
    assert captured["updated_at"].startswith("2024-01-01T00:00:00")
    assert captured["idempotency_key"] == "delivery-1"
    assert captured["deleted"] is False


def test_delete_creates_tombstone_when_no_existing(monkeypatch: pytest.MonkeyPatch) -> None:
    handler = _reload()
    captured: Dict[str, Any] = {}

    def _capture(item: Dict[str, Any]) -> None:
        captured.update(item)

    monkeypatch.setattr(handler, "_fetch_latest_issue_item", lambda key: None)
    monkeypatch.setattr(handler, "_put_item_with_retry", _capture)

    result = handler._handle_delete(_payload())

    assert result["success"] is True
    assert captured["issue_key"] == "MOB-1"
    assert captured["deleted"] is True
    assert captured["idempotency_key"].startswith("delivery-1")


def test_delete_updates_existing_latest(monkeypatch: pytest.MonkeyPatch) -> None:
    handler = _reload()
    captured: Dict[str, Any] = {}

    def _capture(action, params):
        captured.update(params)
        return {}

    monkeypatch.setattr(handler, "_fetch_latest_issue_item", lambda key: {"updated_at": "2024-01-02T00:00:00Z"})
    monkeypatch.setattr(handler, "_execute_with_backoff", _capture)

    handler._handle_delete(_payload(delivery="delivery-2"))

    assert captured["Key"] == {
        "issue_key": "MOB-1",
        "updated_at": "2024-01-02T00:00:00Z",
    }
    assert captured["ExpressionAttributeValues"][":id"].startswith("delivery-2")

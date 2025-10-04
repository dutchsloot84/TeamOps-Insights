from __future__ import annotations

import importlib
import sys
from typing import Any, Dict, List

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("TABLE_NAME", "jira-recon-test")
    yield


def _reload() -> Any:
    module = "services.jira_reconciliation_job.handler"
    if module in sys.modules:
        importlib.reload(sys.modules[module])
    else:
        importlib.import_module(module)
    return importlib.import_module(module)


def _issue(key: str, updated: str) -> Dict[str, Any]:
    return {
        "id": key.replace("MOB-", "100"),
        "key": key,
        "fields": {
            "updated": updated,
            "project": {"key": "MOB"},
            "status": {"name": "In Progress"},
            "assignee": {"displayName": "Jane"},
            "fixVersions": [{"name": "1.0"}],
        },
    }


def test_reconciliation_skips_stale_and_marks_deletes(monkeypatch: pytest.MonkeyPatch) -> None:
    handler = _reload()

    existing_items = [
        {"issue_key": "MOB-1", "updated_at": "2024-01-02T00:00:00Z", "deleted": False},
        {"issue_key": "MOB-2", "updated_at": "2024-01-01T00:00:00Z", "deleted": False},
    ]

    monkeypatch.setattr(handler, "_query_fix_version", lambda fix_version: existing_items)

    created: List[Dict[str, Any]] = []
    deleted: List[str] = []

    def _capture_put(item: Dict[str, Any]) -> None:
        created.append(item)

    def _capture_delete(issue_key: str) -> None:
        deleted.append(issue_key)

    monkeypatch.setattr(handler, "_put_item_with_retry", _capture_put)
    monkeypatch.setattr(handler, "_mark_deleted", _capture_delete)

    issues = [
        _issue("MOB-1", "2024-01-01T00:00:00.000+0000"),
        _issue("MOB-3", "2024-01-04T12:00:00.000+0000"),
    ]

    result = handler._reconcile_fix_version("1.0", issues)

    assert created[0]["issue_key"] == "MOB-3"
    assert created[0]["idempotency_key"].startswith("reconciliation:MOB-3")
    assert deleted == ["MOB-2"]
    assert result["created"] == 1
    assert result["deleted"] == 1
    assert result["updated"] == 0
    assert result["fetched"] == 2

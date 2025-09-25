import importlib
import json
from typing import Any, Dict, List

import pytest


@pytest.fixture(autouse=True)
def _reset_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TABLE_NAME", "test-table")
    monkeypatch.setenv("JIRA_BASE_URL", "https://example.atlassian.net")
    monkeypatch.setenv("FIX_VERSIONS", "")
    monkeypatch.setenv("JQL_TEMPLATE", "fixVersion = '{fix_version}'")
    monkeypatch.setenv("JIRA_SECRET_ARN", "arn:aws:secretsmanager:region:acct:secret")
    monkeypatch.setenv("METRICS_NAMESPACE", "Test/Jira")
    monkeypatch.setenv("RC_DDB_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("RC_DDB_BASE_DELAY", "0.01")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    module = importlib.reload(importlib.import_module("services.jira_reconciliation_job.handler"))
    monkeypatch.setitem(module.__dict__, "_SECRET_CACHE", {"JIRA_EMAIL": "user", "JIRA_API_TOKEN": "token"})
    monkeypatch.setitem(module.__dict__, "_SECRETS", None)


class DummyTable:
    def __init__(self, items: List[Dict[str, Any]] | None = None) -> None:
        self.items = items or []
        self.last_query: List[Dict[str, Any]] = []
        self.put_calls: List[Dict[str, Any]] = []
        self.update_calls: List[Dict[str, Any]] = []
        self.scan_calls = 0

    def query(self, **kwargs: Any) -> Dict[str, Any]:  # pragma: no cover - exercised indirectly
        return {"Items": list(self.items)}

    def scan(self, **kwargs: Any) -> Dict[str, Any]:  # pragma: no cover - exercised indirectly
        self.scan_calls += 1
        return {"Items": [{"fix_version": "2024.05"}], "LastEvaluatedKey": None}

    def put_item(self, **kwargs: Any) -> Dict[str, Any]:  # pragma: no cover - exercised indirectly
        self.put_calls.append(kwargs)
        self.items.append(kwargs.get("Item", {}))
        return {}

    def update_item(self, **kwargs: Any) -> Dict[str, Any]:  # pragma: no cover - exercised indirectly
        self.update_calls.append(kwargs)
        return {}


class DummyCloudWatch:
    def __init__(self) -> None:
        self.metric_payloads: List[Dict[str, Any]] = []

    def put_metric_data(self, Namespace: str, MetricData: List[Dict[str, Any]]) -> None:  # pragma: no cover
        self.metric_payloads.append({"Namespace": Namespace, "MetricData": MetricData})


def _install_table(monkeypatch: pytest.MonkeyPatch, table: DummyTable) -> Any:
    module = importlib.import_module("services.jira_reconciliation_job.handler")
    monkeypatch.setitem(module.__dict__, "_TABLE", table)
    cw = DummyCloudWatch()
    monkeypatch.setitem(module.__dict__, "_CLOUDWATCH", cw)
    return module, cw


def test_reconciliation_upserts_new_issue(monkeypatch: pytest.MonkeyPatch) -> None:
    table = DummyTable()
    module, cw = _install_table(monkeypatch, table)

    def fake_http_request(method: str, url: str, headers=None, data=None) -> str:  # pragma: no cover - exercised indirectly
        payload = {
            "issues": [
                {
                    "id": "1000",
                    "key": "ABC-1",
                    "fields": {
                        "updated": "2024-05-01T12:00:00.000+0000",
                        "project": {"key": "ABC"},
                        "status": {"name": "In Progress"},
                        "assignee": {"displayName": "Ada"},
                        "fixVersions": [{"name": "2024.05"}],
                    },
                }
            ],
            "total": 1,
        }
        return json.dumps(payload)

    monkeypatch.setitem(module.__dict__, "_http_request", fake_http_request)

    response = module.handler({"fixVersions": ["2024.05"]}, None)

    assert response["statusCode"] == 200
    assert table.put_calls
    stored_item = table.put_calls[0]["Item"]
    assert stored_item["issue_id"] == "1000"
    assert stored_item["fix_version"] == "2024.05"
    assert cw.metric_payloads


def test_reconciliation_marks_missing_issue(monkeypatch: pytest.MonkeyPatch) -> None:
    existing = {
        "issue_id": "1000",
        "fix_version": "2024.05",
        "deleted": False,
        "updated_at": "2024-04-01T00:00:00Z",
    }
    table = DummyTable([existing])
    module, _ = _install_table(monkeypatch, table)

    def fake_http_request(method: str, url: str, headers=None, data=None) -> str:  # pragma: no cover - exercised indirectly
        return json.dumps({"issues": [], "total": 0})

    monkeypatch.setitem(module.__dict__, "_http_request", fake_http_request)

    response = module.handler({"fixVersions": ["2024.05"]}, None)

    assert response["statusCode"] == 200
    assert table.update_calls
    update = table.update_calls[0]
    assert update["Key"] == {"issue_id": "1000"}
    assert update["UpdateExpression"].startswith("SET deleted = :true")


def test_reconciliation_discovers_fix_versions_when_not_provided(monkeypatch: pytest.MonkeyPatch) -> None:
    table = DummyTable()
    module, _ = _install_table(monkeypatch, table)

    def fake_http_request(method: str, url: str, headers=None, data=None) -> str:  # pragma: no cover - exercised indirectly
        return json.dumps({"issues": [], "total": 0})

    monkeypatch.setitem(module.__dict__, "_http_request", fake_http_request)

    response = module.handler({}, None)

    assert response["statusCode"] == 200
    assert table.scan_calls >= 1

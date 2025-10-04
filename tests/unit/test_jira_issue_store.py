from __future__ import annotations

from typing import Any, Dict, List

import pytest
from botocore.exceptions import ClientError

from clients.jira_store import JiraIssueStore


class FakeTable:
    def __init__(self, pages: List[Dict[str, Any]]) -> None:
        self.pages = list(pages)
        self.calls: List[Dict[str, Any]] = []

    def query(self, **kwargs: Any) -> Dict[str, Any]:  # pragma: no cover - exercised in tests
        self.calls.append(kwargs)
        if not self.pages:
            return {"Items": []}
        return self.pages.pop(0)


def test_fetch_issues_returns_issue_payloads(monkeypatch: pytest.MonkeyPatch) -> None:
    table = FakeTable(
        [
            {
                "Items": [
                    {
                        "issue_id": "100",
                        "issue_key": "ABC-1",
                        "updated_at": "2024-05-01T12:00:00Z",
                        "issue": {"key": "ABC-1", "fields": {"summary": "First"}},
                        "deleted": False,
                    },
                    {
                        "issue_id": "101",
                        "issue_key": "ABC-2",
                        "updated_at": "2024-05-02T12:00:00Z",
                        "issue": {"key": "ABC-2", "fields": {"summary": "Second"}},
                        "deleted": False,
                    },
                ],
                "LastEvaluatedKey": {
                    "issue_key": "ABC-2",
                    "updated_at": "2024-05-02T12:00:00Z",
                },
            },
            {
                "Items": [
                    {
                        "issue_id": "102",
                        "issue_key": "ABC-3",
                        "updated_at": "2024-05-03T12:00:00Z",
                        "issue": {"key": "ABC-3", "fields": {"summary": "Third"}},
                        "deleted": False,
                    }
                ]
            },
        ]
    )

    store = JiraIssueStore(table_name="table", table_resource=table)
    monkeypatch.setattr(store, "_sleep", lambda *_: None)

    issues, cache_path = store.fetch_issues(fix_version="2024.10.0")

    assert cache_path is None
    assert [issue["key"] for issue in issues] == ["ABC-1", "ABC-2", "ABC-3"]
    assert table.calls[0]["IndexName"] == "FixVersionIndex"


def test_fetch_issues_retries_on_throttle(monkeypatch: pytest.MonkeyPatch) -> None:
    error = ClientError(
        error_response={
            "Error": {"Code": "ProvisionedThroughputExceededException", "Message": "throttle"},
            "ResponseMetadata": {"RequestId": "abc"},
        },
        operation_name="Query",
    )

    class FlakyTable(FakeTable):
        def __init__(self) -> None:
            super().__init__([{ "Items": [] }])
            self.failures = 0

        def query(self, **kwargs: Any) -> Dict[str, Any]:  # pragma: no cover - exercised in tests
            self.calls.append(kwargs)
            if self.failures < 2:
                self.failures += 1
                raise error
            return {"Items": []}

    table = FlakyTable()
    store = JiraIssueStore(table_name="table", table_resource=table)
    sleeps: List[float] = []
    monkeypatch.setattr(store, "_sleep", lambda delay: sleeps.append(delay))

    issues, _ = store.fetch_issues(fix_version="2024.10.0")
    assert issues == []
    assert len(sleeps) == 2


def test_fetch_issues_raises_on_non_retryable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    error = ClientError(
        error_response={
            "Error": {"Code": "ValidationException", "Message": "bad request"},
            "ResponseMetadata": {"RequestId": "xyz"},
        },
        operation_name="Query",
    )

    class BrokenTable(FakeTable):
        def query(self, **kwargs: Any) -> Dict[str, Any]:  # pragma: no cover - exercised in tests
            self.calls.append(kwargs)
            raise error

    store = JiraIssueStore(table_name="table", table_resource=BrokenTable([]))
    with pytest.raises(Exception) as excinfo:
        store.fetch_issues(fix_version="2024.10.0")

    assert "Failed to query Jira issue store" in str(excinfo.value)

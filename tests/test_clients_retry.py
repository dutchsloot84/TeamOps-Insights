from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any

import pytest
import requests

from clients.bitbucket_client import BitbucketClient
from clients.jira_client import JiraClient
from releasecopilot.errors import BitbucketRequestError, JiraQueryError


class DummyResponse:
    def __init__(self, status_code: int, json_data: dict[str, Any] | None = None, *, text: str = "", headers: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text
        self.headers = headers or {}

    def json(self) -> dict[str, Any]:
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)


class FakeSession:
    def __init__(self, responses: list[DummyResponse]) -> None:
        self._responses = responses

    def request(self, method: str, url: str, **_: Any) -> DummyResponse:
        if not self._responses:
            raise AssertionError("No more responses configured")
        return self._responses.pop(0)


class ZeroJitter:
    def uniform(self, _: float, __: float) -> float:  # noqa: D401
        return 0.0


@pytest.fixture(autouse=True)
def reset_logging_handlers() -> None:
    # Ensure each test starts from a clean logging configuration
    from releasecopilot.logging_config import configure_logging

    configure_logging("CRITICAL")


def test_jira_fetch_retries_on_rate_limit(monkeypatch: pytest.MonkeyPatch, tmp_path: Any, caplog: pytest.LogCaptureFixture) -> None:
    responses = [
        DummyResponse(
            429,
            text="Too many requests",
            headers={"Retry-After": "1", "X-RateLimit-Remaining": "0"},
        ),
        DummyResponse(200, json_data={"issues": [], "total": 0}, headers={"X-RateLimit-Remaining": "98"}),
    ]
    client = JiraClient(
        base_url="https://example.atlassian.net",
        access_token="token",
        token_expiry=int(time.time()) + 3600,
        cache_dir=str(tmp_path),
    )
    client.session = FakeSession(responses)  # type: ignore[assignment]
    client._random = ZeroJitter()
    delays: list[float] = []
    monkeypatch.setattr(JiraClient, "_sleep", lambda self, seconds: delays.append(seconds))

    caplog.set_level("DEBUG")
    issues, _ = client.fetch_issues(fix_version="1.0.0")

    assert issues == []
    assert delays and delays[0] >= 1
    retry_logs = [record for record in caplog.records if record.levelname == "WARNING" and record.getMessage() == "Retrying after status"]
    assert retry_logs
    assert getattr(retry_logs[0], "status_code") == 429


def test_jira_fetch_issues_raises_typed_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Any, caplog: pytest.LogCaptureFixture) -> None:
    responses = [
        DummyResponse(500, json_data={}, text="server down")
        for _ in range(5)
    ]
    client = JiraClient(
        base_url="https://example.atlassian.net",
        access_token="token",
        token_expiry=int(time.time()) + 3600,
        cache_dir=str(tmp_path),
    )
    client.session = FakeSession(responses)  # type: ignore[assignment]
    client._random = ZeroJitter()
    delays: list[float] = []
    monkeypatch.setattr(JiraClient, "_sleep", lambda self, seconds: delays.append(seconds))

    caplog.set_level("ERROR")
    with pytest.raises(JiraQueryError) as excinfo:
        client.fetch_issues(fix_version="2.0.0")

    assert excinfo.value.context["status_code"] == 500
    assert "server down" in excinfo.value.context["snippet"]
    assert len(delays) == client._MAX_ATTEMPTS - 1
    assert any(record.getMessage() == "Jira search failed" for record in caplog.records)


def test_bitbucket_retries_and_logs(monkeypatch: pytest.MonkeyPatch, tmp_path: Any, caplog: pytest.LogCaptureFixture) -> None:
    now = datetime.utcnow()
    responses = [
        DummyResponse(429, text="rate limit", headers={"Retry-After": "1"}),
        DummyResponse(200, json_data={"values": [{"hash": "abc"}], "next": None}),
    ]
    client = BitbucketClient(workspace="workspace", cache_dir=str(tmp_path))
    client.session = FakeSession(responses)  # type: ignore[assignment]
    client._random = ZeroJitter()
    delays: list[float] = []
    monkeypatch.setattr(BitbucketClient, "_sleep", lambda self, seconds: delays.append(seconds))

    caplog.set_level("DEBUG")
    commits, _ = client.fetch_commits(
        repositories=["repo"],
        branches=["main"],
        start=now - timedelta(days=1),
        end=now,
    )

    assert commits and commits[0]["hash"] == "abc"
    assert delays and delays[0] >= 1
    assert any(record.getMessage() == "HTTP request" for record in caplog.records)
    assert any(record.getMessage() == "HTTP response" and getattr(record, "repository", None) == "repo" for record in caplog.records)


def test_bitbucket_raises_typed_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Any, caplog: pytest.LogCaptureFixture) -> None:
    now = datetime.utcnow()
    responses = [DummyResponse(503, text="service unavailable") for _ in range(5)]
    client = BitbucketClient(workspace="workspace", cache_dir=str(tmp_path))
    client.session = FakeSession(responses)  # type: ignore[assignment]
    client._random = ZeroJitter()
    delays: list[float] = []
    monkeypatch.setattr(BitbucketClient, "_sleep", lambda self, seconds: delays.append(seconds))

    caplog.set_level("ERROR")
    with pytest.raises(BitbucketRequestError) as excinfo:
        client.fetch_commits(
            repositories=["repo"],
            branches=["main"],
            start=now - timedelta(days=1),
            end=now,
        )

    assert excinfo.value.context["status_code"] == 503
    assert "service unavailable" in excinfo.value.context["snippet"]
    assert len(delays) == client._MAX_ATTEMPTS - 1
    assert any(record.getMessage() == "Bitbucket HTTP error" for record in caplog.records)


def test_retries_can_be_disabled(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    monkeypatch.setenv("RC_DISABLE_RETRIES", "true")
    client = JiraClient(
        base_url="https://example.atlassian.net",
        access_token="token",
        token_expiry=int(time.time()) + 3600,
        cache_dir=str(tmp_path),
    )
    client.session = FakeSession([DummyResponse(500, text="error")])  # type: ignore[assignment]
    client._random = ZeroJitter()
    calls: list[float] = []
    monkeypatch.setattr(JiraClient, "_sleep", lambda self, seconds: calls.append(seconds))

    with pytest.raises(JiraQueryError):
        client.fetch_issues(fix_version="no-retry")

    assert not calls

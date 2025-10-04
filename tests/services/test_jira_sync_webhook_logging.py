import importlib
import json
import sys

import pytest


@pytest.fixture(autouse=True)
def _reset_logging(monkeypatch):
    monkeypatch.setenv("RC_LOG_JSON", "true")
    monkeypatch.setenv("RC_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    if "releasecopilot.logging_config" in sys.modules:
        importlib.reload(sys.modules["releasecopilot.logging_config"])
    else:
        importlib.import_module("releasecopilot.logging_config")
    yield
    # Ensure we clean up handlers between tests
    if "releasecopilot.logging_config" in sys.modules:
        importlib.reload(sys.modules["releasecopilot.logging_config"])


def _reload_module(module_name: str):
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def _collect_logs(capsys):
    output = capsys.readouterr().out.strip().splitlines()
    return [json.loads(line) for line in output if line.strip()]


def test_webhook_handler_redacts_sensitive_event_fields(monkeypatch, capsys):
    monkeypatch.setenv("TABLE_NAME", "jira-webhook-test")
    handler = _reload_module("services.jira_sync_webhook.handler")

    event = {
        "httpMethod": "POST",
        "headers": {"Authorization": "Bearer super-secret-token"},
        "body": json.dumps({"webhookEvent": "unknown", "password": "hunter2"}),
        "isBase64Encoded": False,
    }

    handler.handler(event, None)

    logs = _collect_logs(capsys)
    received = next(payload for payload in logs if payload.get("message") == "Received event")
    event_payload = received["event"]
    assert event_payload["headers"]["Authorization"] == "***REDACTED***"
    assert event_payload["body"] == "***REDACTED***"


def test_reconciliation_handler_redacts_sensitive_event_fields(monkeypatch, capsys):
    monkeypatch.setenv("TABLE_NAME", "jira-recon-test")
    handler = _reload_module("services.jira_reconciliation_job.handler")

    monkeypatch.setattr(handler, "_load_credentials", lambda: handler.JiraCredentials())
    monkeypatch.setattr(handler, "_determine_fix_versions", lambda event: [])

    class _DummySession:
        def __init__(self, base_url, credentials):  # noqa: D401
            self.base_url = base_url
            self.credentials = credentials

        def search(self, jql, *, fields=None):  # noqa: D401
            return []

    monkeypatch.setattr(handler, "JiraSession", _DummySession)

    event = {
        "fixVersions": [],
        "headers": {"Authorization": "Basic super-secret"},
        "client_secret": "abc123-secret",
    }

    handler.handler(event, None)

    logs = _collect_logs(capsys)
    received = next(payload for payload in logs if payload.get("message") == "Starting Jira reconciliation")
    event_payload = received["event"]
    assert event_payload["headers"]["Authorization"] == "***REDACTED***"
    assert event_payload["client_secret"] == "***REDACTED***"

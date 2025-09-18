from __future__ import annotations

import pytest

from releasecopilot import aws_secrets
from releasecopilot.config import resolve_secret


def test_resolve_secret_prefers_existing():
    cfg = {"jira_token": "from-cli", "use_aws_secrets_manager": False}
    assert resolve_secret("jira_token", cfg) == "from-cli"


def test_resolve_secret_falls_back_to_yaml():
    cfg = {
        "use_aws_secrets_manager": False,
        "secrets": {"jira_token": "from-yaml"},
    }
    assert resolve_secret("jira_token", cfg) == "from-yaml"
    assert cfg["jira_token"] == "from-yaml"


def test_resolve_secret_uses_aws(monkeypatch: pytest.MonkeyPatch):
    calls: list[str] = []

    def fake_get_secret(name: str) -> str:
        calls.append(name)
        return "from-aws"

    monkeypatch.setattr(aws_secrets, "get_secret", fake_get_secret)

    cfg: dict[str, object] = {"use_aws_secrets_manager": True}
    assert resolve_secret("jira_token", cfg) == "from-aws"
    assert resolve_secret("jira_token", cfg) == "from-aws"
    assert calls == ["jira_token"]

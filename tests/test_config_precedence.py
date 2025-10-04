"""Configuration precedence and validation tests for the layered loader."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.config.loader import ConfigurationError, load_config

from tests.helpers_config import StubCredentialStore, write_defaults


def test_cli_overrides_have_highest_precedence(tmp_path: Path) -> None:
    defaults = write_defaults(tmp_path)
    secrets = StubCredentialStore({"arn:example:jira": {"client_id": "secret-client"}})
    env = {"JIRA_CLIENT_ID": "env-client", "AWS_REGION": "us-override-1"}

    config = load_config(
        defaults_path=defaults,
        env=env,
        credential_store=secrets,
        override_path=tmp_path / "settings.yaml",
        overrides={"jira": {"credentials": {"client_id": "cli-client"}}},
    )

    assert config["jira"]["credentials"]["client_id"] == "cli-client"
    assert config["aws"]["region"] == "us-override-1"


def test_missing_required_values_raise(tmp_path: Path) -> None:
    defaults = write_defaults(tmp_path, missing_bucket=True)
    secrets = StubCredentialStore()

    with pytest.raises(ConfigurationError) as excinfo:
        load_config(
            defaults_path=defaults,
            credential_store=secrets,
            override_path=tmp_path / "settings.yaml",
        )

    assert "storage.s3.bucket" in str(excinfo.value)


def test_environment_overrides_secret_values(tmp_path: Path) -> None:
    defaults = write_defaults(tmp_path)
    secrets = StubCredentialStore({"arn:example:jira": {"client_secret": "secret-value"}})
    env = {"JIRA_CLIENT_SECRET": "env-value"}

    config = load_config(
        defaults_path=defaults,
        credential_store=secrets,
        env=env,
        override_path=tmp_path / "settings.yaml",
    )

    assert config["jira"]["credentials"]["client_secret"] == "env-value"

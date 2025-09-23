"""Configuration precedence and validation tests."""
from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from releasecopilot.config import ConfigError, build_config, load_yaml_defaults


def _namespace(**overrides: object) -> argparse.Namespace:
    """Helper to construct CLI namespaces with sensible defaults."""

    defaults = {
        "config": None,
        "fix_version": None,
        "jira_base": None,
        "bitbucket_base": None,
        "jira_user": None,
        "jira_token": None,
        "bitbucket_token": None,
        "use_aws_secrets_manager": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_load_yaml_defaults_reads_mapping(tmp_path: Path) -> None:
    """``load_yaml_defaults`` should load structured data from YAML files."""

    config_file = tmp_path / "releasecopilot.yaml"
    config_file.write_text(
        """
        fix_version: 2.3.4
        jira_base: https://jira.example.com
        bitbucket_base: https://bitbucket.example.com
        use_aws_secrets_manager: false
        """
    )

    data = load_yaml_defaults(config_file)
    assert data["fix_version"] == "2.3.4"
    assert data["jira_base"] == "https://jira.example.com"
    assert data["bitbucket_base"] == "https://bitbucket.example.com"
    assert data["use_aws_secrets_manager"] is False


def test_environment_variables_override_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables should take precedence over YAML defaults."""

    config_file = tmp_path / "releasecopilot.yaml"
    config_file.write_text(
        """
        fix_version: 1.0.0
        jira_base: https://jira-from-file
        bitbucket_base: https://bitbucket-from-file
        jira_user: example@example.com
        use_aws_secrets_manager: false
        """
    )

    monkeypatch.setenv("RELEASECOPILOT_JIRA_BASE", "https://jira-from-env")
    monkeypatch.setenv("BITBUCKET_BASE", "https://bitbucket-from-env")
    monkeypatch.setenv("USE_AWS_SECRETS_MANAGER", "true")

    args = _namespace(config=str(config_file))
    config = build_config(args)

    assert config["config_path"] == str(config_file)
    assert config["jira_base"] == "https://jira-from-env"
    assert config["bitbucket_base"] == "https://bitbucket-from-env"
    assert config["use_aws_secrets_manager"] is True


def test_cli_arguments_override_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """CLI arguments supplied by the user should have the highest precedence."""

    config_file = tmp_path / "releasecopilot.yaml"
    config_file.write_text(
        """
        fix_version: 3.0.0
        jira_base: https://jira-from-file
        bitbucket_base: https://bitbucket-from-file
        use_aws_secrets_manager: false
        """
    )

    monkeypatch.setenv("JIRA_BASE", "https://jira-from-env")

    args = _namespace(
        config=str(config_file),
        jira_base="https://jira-from-cli",
        fix_version="9.9.9",
    )
    config = build_config(args)

    assert config["jira_base"] == "https://jira-from-cli"
    assert config["fix_version"] == "9.9.9"


def test_missing_required_fields_raise_config_error(tmp_path: Path) -> None:
    """Missing required configuration values should raise ``ConfigError``."""

    config_file = tmp_path / "releasecopilot.yaml"
    config_file.write_text(
        """
        jira_base: https://jira.example.com
        use_aws_secrets_manager: false
        """
    )

    args = _namespace(config=str(config_file))
    with pytest.raises(ConfigError) as excinfo:
        build_config(args)

    message = str(excinfo.value)
    assert "fix_version" in message
    assert "bitbucket_base" in message


def test_invalid_yaml_type_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Non-mapping YAML content should surface as a ``ConfigError``."""

    config_file = tmp_path / "releasecopilot.yaml"
    config_file.write_text("- not-a-mapping\n- still-not-a-mapping\n")

    args = _namespace(config=str(config_file))

    with pytest.raises(ConfigError):
        build_config(args)


def test_environment_boolean_coercion(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Boolean configuration keys should respect truthy/falsy environment values."""

    config_file = tmp_path / "releasecopilot.yaml"
    config_file.write_text(
        """
        fix_version: 1.2.3
        jira_base: https://jira.example.com
        bitbucket_base: https://bitbucket.example.com
        use_aws_secrets_manager: false
        """
    )

    monkeypatch.setenv("USE_AWS_SECRETS_MANAGER", "0")

    args = _namespace(config=str(config_file), use_aws_secrets_manager=True)
    config = build_config(args)

    assert config["use_aws_secrets_manager"] is True

    monkeypatch.delenv("USE_AWS_SECRETS_MANAGER")
    args = _namespace(config=str(config_file))
    config = build_config(args)
    assert config["use_aws_secrets_manager"] is False

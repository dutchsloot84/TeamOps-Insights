"""CLI parsing tests for Release Copilot."""
from __future__ import annotations

from pathlib import Path

from releasecopilot import cli


def test_parse_args_supports_boolean_flags() -> None:
    """The CLI should toggle the AWS Secrets Manager flag correctly."""

    args = cli.parse_args(["--use-aws-secrets-manager"])
    assert args.use_aws_secrets_manager is True

    args = cli.parse_args(["--no-aws-secrets-manager"])
    assert args.use_aws_secrets_manager is False


def test_parse_args_records_config_path(tmp_path: Path) -> None:
    """Supplying ``--config`` should preserve the provided path."""

    config_path = tmp_path / "custom.yaml"
    args = cli.parse_args(["--config", str(config_path)])
    assert Path(args.config) == config_path


def test_run_builds_config_from_yaml(tmp_path: Path) -> None:
    """``cli.run`` should integrate with ``build_config`` to produce a final mapping."""

    config_file = tmp_path / "releasecopilot.yaml"
    config_file.write_text(
        """
        fix_version: 8.8.8
        jira_base: https://jira.cli
        bitbucket_base: https://bitbucket.cli
        use_aws_secrets_manager: false
        """
    )

    result = cli.run(["--config", str(config_file)])

    assert result["fix_version"] == "8.8.8"
    assert result["jira_base"] == "https://jira.cli"
    assert result["bitbucket_base"] == "https://bitbucket.cli"
    assert result["config_path"] == str(config_file)

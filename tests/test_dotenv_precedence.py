from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytest

pytest.importorskip("dotenv")


def test_cli_prefers_cli_then_env_then_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env_path = repo_root / ".env"

    existing_env = env_path.read_text() if env_path.exists() else None
    env_path.write_text(
        "\n".join(
            [
                "JIRA_BASE=https://dotenv-jira",
                "BITBUCKET_BASE=https://dotenv-bitbucket",
                "FIX_VERSION=from-dotenv",
                "",
            ]
        )
    )

    for key in ("JIRA_BASE", "BITBUCKET_BASE", "FIX_VERSION"):
        monkeypatch.delenv(key, raising=False)

    try:
        sys.modules.pop("releasecopilot", None)
        sys.modules.pop("releasecopilot.cli", None)
        import releasecopilot.cli as cli_module  # noqa: WPS433

        assert cli_module.load_dotenv is not None
        assert (Path(cli_module.__file__).resolve().parents[2] / ".env") == env_path

        cli_module._load_local_dotenv()

        yaml_path = tmp_path / "releasecopilot.yaml"
        yaml_path.write_text(
            "\n".join(
                [
                    "fix_version: from-yaml",
                    "jira_base: https://yaml-jira",
                    "bitbucket_base: https://yaml-bitbucket",
                    "",
                ]
            )
        )

        args = argparse.Namespace(
            config=str(yaml_path),
            fix_version="from-cli",
            jira_base="https://cli-jira",
            bitbucket_base=None,
            jira_user=None,
            jira_token=None,
            bitbucket_token=None,
            use_aws_secrets_manager=None,
        )

        import os

        assert os.environ["BITBUCKET_BASE"] == "https://dotenv-bitbucket"

        config = cli_module.build_config(args)

        assert config["fix_version"] == "from-cli"
        assert config["jira_base"] == "https://cli-jira"
        assert config["bitbucket_base"] == "https://dotenv-bitbucket"
    finally:
        sys.modules.pop("releasecopilot", None)
        sys.modules.pop("releasecopilot.cli", None)
        if existing_env is None:
            env_path.unlink(missing_ok=True)
        else:
            env_path.write_text(existing_env)
        for key in ("JIRA_BASE", "BITBUCKET_BASE", "FIX_VERSION"):
            monkeypatch.delenv(key, raising=False)

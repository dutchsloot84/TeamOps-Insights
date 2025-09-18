from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from releasecopilot.config import build_config, merge_configs


def test_merge_configs_precedence():
    low = {"key": "low", "other": "base"}
    mid = {"key": "mid"}
    high = {"key": "high"}
    merged = merge_configs(high, mid, low)
    assert merged["key"] == "high"
    assert merged["other"] == "base"


def test_build_config_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    yaml_path = tmp_path / "releasecopilot.yaml"
    yaml_path.write_text(
        """
fix_version: 1.0.0
jira_base: https://yaml-jira
bitbucket_base: https://yaml-bitbucket
"""
    )

    monkeypatch.setenv("JIRA_BASE", "https://env-jira")
    monkeypatch.setenv("FIX_VERSION", "2.0.0")

    args = argparse.Namespace(
        config=str(yaml_path),
        fix_version="3.0.0",
        jira_base="https://cli-jira",
        bitbucket_base=None,
        jira_user=None,
        jira_token=None,
        bitbucket_token=None,
        use_aws_secrets_manager=None,
    )

    config = build_config(args)

    assert config["jira_base"] == "https://cli-jira"
    assert config["fix_version"] == "3.0.0"
    assert config["bitbucket_base"] == "https://yaml-bitbucket"


def test_build_config_env_over_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    yaml_path = tmp_path / "releasecopilot.yaml"
    yaml_path.write_text(
        """
fix_version: 1.0.0
jira_base: https://yaml-jira
bitbucket_base: https://yaml-bitbucket
"""
    )

    monkeypatch.setenv("BITBUCKET_BASE", "https://env-bitbucket")
    monkeypatch.setenv("FIX_VERSION", "2.0.0")

    args = argparse.Namespace(
        config=str(yaml_path),
        fix_version=None,
        jira_base=None,
        bitbucket_base=None,
        jira_user=None,
        jira_token=None,
        bitbucket_token=None,
        use_aws_secrets_manager=None,
    )

    config = build_config(args)

    assert config["bitbucket_base"] == "https://env-bitbucket"
    assert config["fix_version"] == "2.0.0"
    assert config["jira_base"] == "https://yaml-jira"

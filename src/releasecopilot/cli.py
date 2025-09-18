"""Command line interface for Release Copilot configuration."""
from __future__ import annotations

import argparse
from typing import Iterable, Optional

from .config import build_config


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Release Copilot configuration")
    parser.add_argument(
        "--config",
        help="Path to a releasecopilot.yaml file (defaults to ./releasecopilot.yaml if present)",
    )
    parser.add_argument("--fix-version", dest="fix_version", help="Fix version to operate on")
    parser.add_argument(
        "--jira-base",
        dest="jira_base",
        help="Base URL of the Jira instance (e.g. https://example.atlassian.net)",
    )
    parser.add_argument(
        "--bitbucket-base",
        dest="bitbucket_base",
        help="Base URL of the Bitbucket workspace",
    )
    parser.add_argument("--jira-user", dest="jira_user", help="Jira username or email")
    parser.add_argument("--jira-token", dest="jira_token", help="Jira API token or password")
    parser.add_argument(
        "--bitbucket-token",
        dest="bitbucket_token",
        help="Bitbucket access token or app password",
    )
    parser.add_argument(
        "--use-aws-secrets-manager",
        dest="use_aws_secrets_manager",
        action="store_true",
        default=None,
        help="Enable AWS Secrets Manager fallback when secrets are missing",
    )
    parser.add_argument(
        "--no-aws-secrets-manager",
        dest="use_aws_secrets_manager",
        action="store_false",
        help=argparse.SUPPRESS,
    )
    return parser


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments into a namespace."""

    parser = _create_parser()
    return parser.parse_args(argv)


def run(argv: Optional[Iterable[str]] = None) -> dict:
    """Parse arguments and build the resulting configuration dictionary."""

    args = parse_args(argv)
    return build_config(args)


__all__ = ["parse_args", "run", "build_config"]

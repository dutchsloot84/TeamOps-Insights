"""Command line interface for Release Copilot configuration."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Optional

from releasecopilot.logging_config import configure_logging, get_logger

try:  # pragma: no cover - optional dependency
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None


from .config import build_config


def _load_local_dotenv() -> None:
    """Best-effort loading of a project-level ``.env`` file."""

    if load_dotenv is None:
        return

    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.is_file():
        return

    try:  # pragma: no cover - defensive guard around optional dependency
        load_dotenv(dotenv_path=env_path)
    except Exception:
        # Loading environment variables is a convenience for local usage and
        # should never break the CLI if anything goes wrong.
        pass


_load_local_dotenv()


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
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    return parser


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments into a namespace."""

    parser = _create_parser()
    return parser.parse_args(argv)


def run(argv: Optional[Iterable[str]] = None) -> dict:
    """Parse arguments and build the resulting configuration dictionary."""

    args = parse_args(argv)
    configure_logging(args.log_level)
    logger = get_logger(__name__)
    logger.debug("CLI arguments parsed", extra={"args": {k: v for k, v in vars(args).items() if v is not None}})
    return build_config(args)


__all__ = ["parse_args", "run", "build_config"]

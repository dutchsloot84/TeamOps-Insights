"""ReleaseCopilot CLI dispatcher for subcommands such as ``rc audit``."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable

from releasecopilot.logging_config import configure_logging, get_logger

from ..config.loader import Defaults, load_defaults
from .audit import AuditInputError, AuditOptions, AuditResult, run_audit
from .health import HealthCommandError, register_health_parser, run_health_command

LOGGER = get_logger(__name__)


def _scope_entry(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError(
            f"Scope values must follow key=value format (received {value!r})"
        )
    key, parsed = value.split("=", 1)
    return key.strip(), parsed.strip()


def _build_audit_parser(subparsers: argparse._SubParsersAction, defaults: Defaults) -> None:
    audit = subparsers.add_parser(
        "audit",
        help="Generate release audit artifacts from cached payloads",
    )
    audit.add_argument(
        "--cache-dir",
        default=str(defaults.cache_dir),
        help="Directory containing cached Jira/Bitbucket payloads",
    )
    audit.add_argument(
        "--json",
        default=str((defaults.artifact_dir / "audit.json")),
        help="Path where the JSON artifact will be written",
    )
    audit.add_argument(
        "--xlsx",
        default=str((defaults.artifact_dir / "audit.xlsx")),
        help="Path where the Excel artifact will be written",
    )
    audit.add_argument(
        "--summary",
        default=str((defaults.artifact_dir / "audit-summary.json")),
        help="Path where the summary JSON should be stored",
    )
    audit.add_argument(
        "--scope",
        action="append",
        default=[],
        type=_scope_entry,
        help="Key=value metadata entries describing the audit scope",
    )
    audit.add_argument(
        "--upload",
        help="Optional S3 destination (e.g. s3://bucket/prefix)",
    )
    audit.add_argument(
        "--region",
        help="AWS region for uploads (defaults to AWS_REGION/AWS_DEFAULT_REGION)",
    )
    audit.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the execution plan without reading caches or writing files",
    )
    audit.add_argument(
        "--log-level",
        default="INFO",
        help="Logging verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )


def build_parser(defaults: Defaults | None = None) -> argparse.ArgumentParser:
    defaults = defaults or load_defaults()
    parser = argparse.ArgumentParser(prog="rc", description="ReleaseCopilot CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _build_audit_parser(subparsers, defaults)
    register_health_parser(subparsers, defaults)
    return parser


def _collect_audit_options(args: argparse.Namespace, defaults: Defaults) -> AuditOptions:
    scope: dict[str, str] = {}
    for key, value in args.scope:
        scope[key] = value
    region = args.region or _default_region()
    return AuditOptions(
        cache_dir=Path(args.cache_dir),
        json_path=Path(args.json),
        excel_path=Path(args.xlsx),
        summary_path=Path(args.summary),
        scope=scope,
        upload_uri=args.upload,
        region=region,
        dry_run=args.dry_run,
        defaults=defaults,
    )


def _default_region() -> str | None:
    for key in ("AWS_REGION", "AWS_DEFAULT_REGION"):
        value = os.environ.get(key)
        if value:
            return value
    return None


def main(argv: Iterable[str] | None = None, *, defaults: Defaults | None = None) -> int:
    defaults = defaults or load_defaults()
    parser = build_parser(defaults)
    args = parser.parse_args(argv)

    configure_logging(getattr(args, "log_level", "INFO"))
    LOGGER.debug("Parsed arguments", extra={"command": args.command})

    if args.command == "audit":
        options = _collect_audit_options(args, defaults)

        try:
            if args.dry_run:
                plan = options.build_plan()
                print(json.dumps({"plan": plan}, indent=2))
                return 0

            result: AuditResult = run_audit(options)
        except AuditInputError as exc:
            LOGGER.error("Audit command failed", extra={"error": str(exc)})
            print(str(exc), file=sys.stderr)
            return 1

        print(json.dumps(result.as_dict(), indent=2))
        return 0

    if args.command == "health":
        try:
            return run_health_command(args, defaults)
        except HealthCommandError as exc:
            LOGGER.error("Health command failed", extra={"error": str(exc)})
            print(str(exc), file=sys.stderr)
            return 1

    parser.print_help()
    return 1


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())

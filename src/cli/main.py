"""Modern CLI shim for ``python -m src.cli.main`` usage."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Iterable, Optional

try:
    from main import AuditConfig, run_audit
except ModuleNotFoundError:
    fallback_root = Path(__file__).resolve().parents[2]
    if str(fallback_root) not in sys.path:
        sys.path.insert(0, str(fallback_root))
    fallback_src = fallback_root / "src"
    if str(fallback_src) not in sys.path:
        sys.path.insert(1, str(fallback_src))
    from main import AuditConfig, run_audit

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(1, str(SRC_PATH))

try:  # pragma: no cover - optional dependency loading
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

from releasecopilot.errors import ReleaseCopilotError  # noqa: E402
from releasecopilot.logging_config import configure_logging, get_logger  # noqa: E402

logger = get_logger(__name__)

def _copy_artifacts(artifacts: dict[str, str], destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for _, src in artifacts.items():
        if not src:
            continue
        source_path = Path(src)
        if not source_path.exists():
            continue
        shutil.copy2(source_path, destination / source_path.name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ReleaseCopilot audit runner")
    parser.add_argument("--fix-version", required=True, help="Jira fix version to audit")
    parser.add_argument("--repos", nargs="*", default=[], help="Bitbucket repositories to inspect")
    parser.add_argument("--branches", nargs="*", help="Optional branches to include")
    parser.add_argument("--develop-only", action="store_true", help="Use the develop branch only")
    parser.add_argument("--freeze-date", help="ISO freeze date override")
    parser.add_argument("--window-days", type=int, default=28, help="Lookback window in days")
    parser.add_argument("--use-cache", action="store_true", help="Reuse cached payloads")
    parser.add_argument("--s3-bucket", help="Override destination S3 bucket")
    parser.add_argument("--s3-prefix", help="Override destination S3 prefix")
    parser.add_argument("--output-prefix", default="audit_results", help="Basename for generated files")
    parser.add_argument("--output", help="Optional directory to copy generated artifacts into")
    parser.add_argument("--format", choices=["json", "excel", "both"], default="both", help="Artifact copy format")
    parser.add_argument("--dry-run", action="store_true", help="Skip remote calls and only echo configuration")
    parser.add_argument("--log-level", default="INFO", help="Logging verbosity")
    return parser


def parse_args(argv: Optional[Iterable[str]] = None) -> tuple[argparse.Namespace, AuditConfig]:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = AuditConfig(
        fix_version=args.fix_version,
        repos=list(args.repos),
        branches=list(args.branches) if args.branches else None,
        window_days=args.window_days,
        freeze_date=args.freeze_date,
        develop_only=args.develop_only,
        use_cache=args.use_cache,
        s3_bucket=args.s3_bucket or os.getenv("ARTIFACTS_BUCKET"),
        s3_prefix=args.s3_prefix,
        output_prefix=args.output_prefix,
    )
    return args, config


def main(argv: Optional[Iterable[str]] = None) -> int:
    args, config = parse_args(argv)
    configure_logging(args.log_level)
    logger.info(
        "Starting ReleaseCopilot run",
        extra={
            "fix_version": config.fix_version,
            "repos": config.repos,
            "branches": config.branches,
        },
    )

    if args.dry_run:
        logger.info("Dry run requested")
        print(json.dumps({"config": config.__dict__}, indent=2))
        return 0

    try:
        result = run_audit(config)
    except ReleaseCopilotError as exc:
        logger.error("ReleaseCopilot run failed", extra=getattr(exc, "context", {}))
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    artifacts = result.get("artifacts", {})

    destination: Optional[Path] = Path(args.output) if args.output else None
    if destination:
        selected = {}
        for name, artifact_path in artifacts.items():
            if not artifact_path:
                continue
            suffix = Path(artifact_path).suffix.lower()
            if args.format == "json" and suffix != ".json":
                continue
            if args.format == "excel" and suffix != ".xlsx":
                continue
            selected[name] = artifact_path
        if selected:
            _copy_artifacts(selected, destination)
        summary_path = destination / "summary.json"
        summary_path.write_text(json.dumps(result.get("summary", {}), indent=2), encoding="utf-8")

    logger.info("ReleaseCopilot run completed", extra={"artifacts": list(artifacts.keys())})
    print(json.dumps(result.get("summary", {}), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())

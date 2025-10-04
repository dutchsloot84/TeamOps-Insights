"""CLI entry point for releasecopilot-ai."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:  # pragma: no cover - best effort optional dependency
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - ignore missing dependency
    load_dotenv = None


from clients.bitbucket_client import BitbucketClient
from clients.jira_client import JiraClient, compute_fix_version_window
from clients.jira_store import JiraIssueStore
from config.settings import load_settings
from exporters.excel_exporter import ExcelExporter
from exporters.json_exporter import JSONExporter
from processors.audit_processor import AuditProcessor
from releasecopilot import uploader
from releasecopilot.errors import ReleaseCopilotError
from releasecopilot.logging_config import configure_logging, get_logger


def _load_local_dotenv() -> None:
    if load_dotenv is None:
        return

    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.is_file():
        return

    try:  # pragma: no cover - defensive guard
        load_dotenv(dotenv_path=env_path)
    except Exception:
        pass


_load_local_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
TEMP_DIR = BASE_DIR / "temp_data"


@dataclass
class AuditConfig:
    fix_version: str
    repos: List[str] = field(default_factory=list)
    branches: Optional[List[str]] = None
    window_days: int = 28
    freeze_date: Optional[str] = None
    develop_only: bool = False
    use_cache: bool = False
    s3_bucket: Optional[str] = None
    s3_prefix: Optional[str] = None
    output_prefix: str = "audit_results"


def parse_args(argv: Optional[Iterable[str]] = None) -> tuple[argparse.Namespace, AuditConfig]:
    parser = argparse.ArgumentParser(description="Releasecopilot AI")
    parser.add_argument("--fix-version", required=True, help="Fix version to audit")
    parser.add_argument("--repos", nargs="*", default=[], help="Bitbucket repositories to inspect")
    parser.add_argument("--branches", nargs="*", help="Branches to include")
    parser.add_argument("--develop-only", action="store_true", help="Shortcut for using the develop branch only")
    parser.add_argument("--freeze-date", help="ISO formatted freeze date (YYYY-MM-DD)")
    parser.add_argument("--window-days", type=int, default=28, help="Days before freeze date to include commits")
    parser.add_argument("--use-cache", action="store_true", help="Reuse cached API responses where available")
    parser.add_argument("--s3-bucket", help="Override the default S3 bucket")
    parser.add_argument("--s3-prefix", help="Override the default S3 prefix")
    parser.add_argument("--output-prefix", default="audit_results", help="Basename for output files")
    parser.add_argument("--log-level", default="INFO", help="Logging verbosity")

    args = parser.parse_args(argv)

    config = AuditConfig(
        fix_version=args.fix_version,
        repos=args.repos,
        branches=args.branches,
        window_days=args.window_days,
        freeze_date=args.freeze_date,
        develop_only=args.develop_only,
        use_cache=args.use_cache,
        s3_bucket=args.s3_bucket,
        s3_prefix=args.s3_prefix,
        output_prefix=args.output_prefix,
    )
    return args, config


def run_audit(config: AuditConfig) -> Dict[str, Any]:
    logger = get_logger(__name__)

    overrides: Dict[str, Any] = {}
    if config.s3_bucket or config.s3_prefix:
        overrides.setdefault("storage", {}).setdefault("s3", {})
        if config.s3_bucket:
            overrides["storage"]["s3"]["bucket"] = config.s3_bucket
        if config.s3_prefix:
            overrides["storage"]["s3"]["prefix"] = config.s3_prefix

    settings = load_settings(overrides=overrides)
    region = settings.get("aws", {}).get("region")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    jira_store = build_jira_store(settings)
    bitbucket_client = build_bitbucket_client(settings)

    freeze_dt = parse_freeze_date(config.freeze_date)
    window = compute_fix_version_window(freeze_dt, config.window_days)

    branches = determine_branches(config, settings)
    repos = determine_repos(config, settings)

    logger.info(
        "Starting audit",
        extra={
            "fix_version": config.fix_version,
            "repos": repos,
            "branches": branches,
            "window": {"start": window["start"].isoformat(), "end": window["end"].isoformat()},
        },
    )

    issues, jira_cache_path = jira_store.fetch_issues(
        fix_version=config.fix_version,
        use_cache=config.use_cache,
    )
    jira_output = DATA_DIR / "jira_issues.json"
    write_json(jira_output, {"fixVersion": config.fix_version, "issues": issues})

    commits, cache_keys = bitbucket_client.fetch_commits(
        repositories=repos,
        branches=branches,
        start=window["start"],
        end=window["end"],
        use_cache=config.use_cache,
    )
    commits_output = DATA_DIR / "bitbucket_commits.json"
    write_json(commits_output, {"repos": repos, "branches": branches, "commits": commits})

    processor = AuditProcessor(issues=issues, commits=commits)
    audit_result = processor.process()

    audit_payload = {
        "summary": audit_result.summary,
        "stories_with_no_commits": audit_result.stories_with_no_commits,
        "orphan_commits": audit_result.orphan_commits,
        "commit_story_mapping": audit_result.commit_story_mapping,
    }

    json_exporter = JSONExporter(DATA_DIR)
    excel_exporter = ExcelExporter(DATA_DIR)

    json_path = json_exporter.export(audit_payload, f"{config.output_prefix}.json")
    excel_path = excel_exporter.export(audit_payload, f"{config.output_prefix}.xlsx")

    summary_path = DATA_DIR / "summary.json"
    write_json(summary_path, audit_result.summary)

    artifacts = {
        "jira_issues": str(jira_output),
        "bitbucket_commits": str(commits_output),
        "json_report": str(json_path),
        "excel_report": str(excel_path),
        "summary": str(summary_path),
    }

    report_files: List[Path] = [json_path, excel_path, summary_path]

    # Collect raw payload cache files for optional S3 upload
    raw_files: List[Path] = [jira_output, commits_output]
    raw_cache_sources: List[Path] = [path for path in [jira_cache_path] if path]
    raw_files.extend(raw_cache_sources)
    for cache_key in cache_keys:
        cache_file = bitbucket_client.get_last_cache_file(cache_key)
        if cache_file:
            raw_files.append(cache_file)

    upload_artifacts(
        config=config,
        settings=settings,
        reports=report_files,
        raw_files=raw_files,
        region=region,
    )

    logger.info("Audit finished", extra={"summary": audit_result.summary})
    return {"summary": audit_result.summary, "artifacts": artifacts}


def build_jira_client(settings: Dict[str, Any]) -> JiraClient:
    jira_cfg = settings.get("jira", {})

    base_url = jira_cfg.get("base_url")
    if not base_url:
        raise RuntimeError("Jira base URL is not configured")

    credentials = jira_cfg.get("credentials", {})
    token_expiry_raw = credentials.get("token_expiry")
    token_expiry = int(token_expiry_raw) if token_expiry_raw else None

    return JiraClient(
        base_url=base_url,
        client_id=credentials.get("client_id"),
        client_secret=credentials.get("client_secret"),
        access_token=credentials.get("access_token"),
        refresh_token=credentials.get("refresh_token"),
        token_expiry=token_expiry,
        cache_dir=TEMP_DIR / "jira",
    )


def build_jira_store(settings: Dict[str, Any]) -> JiraIssueStore:
    storage_cfg = settings.get("storage", {})
    table_name = (
        storage_cfg.get("dynamodb", {}).get("jira_issue_table")
        or settings.get("jira", {}).get("issue_table_name")
    )
    if not table_name:
        raise RuntimeError("Jira issue DynamoDB table name is not configured")

    region = settings.get("aws", {}).get("region")
    return JiraIssueStore(table_name=table_name, region_name=region)


def build_bitbucket_client(settings: Dict[str, Any]) -> BitbucketClient:
    bitbucket_cfg = settings.get("bitbucket", {})

    workspace = bitbucket_cfg.get("workspace")
    if not workspace:
        raise RuntimeError("Bitbucket workspace is not configured")

    credentials = bitbucket_cfg.get("credentials", {})

    return BitbucketClient(
        workspace=workspace,
        username=credentials.get("username"),
        app_password=credentials.get("app_password"),
        access_token=credentials.get("access_token"),
        cache_dir=TEMP_DIR / "bitbucket",
    )


def determine_branches(config: AuditConfig, settings: Dict[str, Any]) -> List[str]:
    if config.develop_only:
        return ["develop"]
    if config.branches:
        return config.branches
    return settings.get("bitbucket", {}).get("default_branches", ["main"])


def determine_repos(config: AuditConfig, settings: Dict[str, Any]) -> List[str]:
    if config.repos:
        return config.repos
    return settings.get("bitbucket", {}).get("repositories", [])


def parse_freeze_date(raw: Optional[str]) -> datetime:
    if not raw:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return datetime.strptime(raw, "%Y-%m-%d")


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


def upload_artifacts(
    *,
    config: AuditConfig,
    settings: Dict[str, Any],
    reports: Iterable[Path],
    raw_files: Iterable[Path],
    region: Optional[str],
) -> None:
    logger = get_logger(__name__)
    bucket = (
        config.s3_bucket
        or settings.get("storage", {}).get("s3", {}).get("bucket")
        or os.getenv("ARTIFACTS_BUCKET")
    )
    if not bucket:
        logger.info("No S3 bucket configured; skipping artifact upload.")
        return

    prefix_root = (
        config.s3_prefix
        or settings.get("storage", {}).get("s3", {}).get("prefix")
        or os.getenv("ARTIFACTS_PREFIX")
        or "releasecopilot"
    )
    prefix_root = prefix_root.strip("/")
    if not prefix_root:
        prefix_root = "releasecopilot"

    timestamp_source = datetime.utcnow()
    timestamp = timestamp_source.strftime("%Y-%m-%d_%H%M%S")
    generated_at = timestamp_source.replace(microsecond=0).isoformat() + "Z"
    prefix = "/".join([prefix_root, config.fix_version, timestamp])

    metadata = {
        "fix-version": config.fix_version,
        "generated-at": generated_at,
    }
    git_sha = _detect_git_sha()
    if git_sha:
        metadata["git-sha"] = git_sha

    staging_root = TEMP_DIR / "s3_staging" / timestamp
    reports_dir = staging_root / "reports"
    raw_dir = staging_root / "raw"

    _stage_files(reports_dir, reports)
    _stage_files(raw_dir, raw_files)

    client = uploader.build_s3_client(region_name=region)

    uploader.upload_directory(
        bucket=bucket,
        prefix=prefix,
        local_dir=reports_dir,
        subdir="reports",
        client=client,
        metadata=metadata,
    )
    uploader.upload_directory(
        bucket=bucket,
        prefix=prefix,
        local_dir=raw_dir,
        subdir="raw",
        client=client,
        metadata=metadata,
    )


def _stage_files(target_dir: Path, sources: Iterable[Path]) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    counters: Dict[str, int] = {}
    for source in sources:
        if not source:
            continue
        path = Path(source)
        if not path.exists() or not path.is_file():
            continue
        name = path.name
        if name in counters:
            counters[name] += 1
            stem = path.stem
            suffix = path.suffix
            name = f"{stem}_{counters[name]}{suffix}"
        else:
            counters[name] = 0
        destination = target_dir / name
        shutil.copy2(path, destination)


def _detect_git_sha() -> Optional[str]:
    try:
        output = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        return None
    sha = output.decode("utf-8").strip()
    return sha or None


if __name__ == "__main__":
    args, config = parse_args()
    configure_logging(args.log_level)
    try:
        run_audit(config)
    except ReleaseCopilotError as exc:
        logger = get_logger(__name__)
        logger.error("Audit execution failed", extra=getattr(exc, "context", {}))
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

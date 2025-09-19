"""CLI entry point for releasecopilot-ai."""
from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:  # pragma: no cover - best effort optional dependency
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - ignore missing dependency
    load_dotenv = None


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

from aws import s3_utils
from clients.bitbucket_client import BitbucketClient
from clients.jira_client import JiraClient, compute_fix_version_window
from clients.secrets_manager import CredentialStore, SecretsManager
from config.settings import load_settings
from exporters.excel_exporter import ExcelExporter
from exporters.json_exporter import JSONExporter
from processors.audit_processor import AuditProcessor

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
    upload_s3: bool = False
    use_cache: bool = False
    s3_bucket: Optional[str] = None
    s3_prefix: Optional[str] = None
    output_prefix: str = "audit_results"


def setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]


class JsonFormatter(logging.Formatter):
    """Formats logs as JSON for CloudWatch-friendly output."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in {"args", "msg", "levelname", "levelno", "pathname", "filename", "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created", "msecs", "relativeCreated", "thread", "threadName", "processName", "process", "message"}:
                continue
            payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def parse_args(argv: Optional[Iterable[str]] = None) -> AuditConfig:
    parser = argparse.ArgumentParser(description="Releasecopilot AI")
    parser.add_argument("--fix-version", required=True, help="Fix version to audit")
    parser.add_argument("--repos", nargs="*", default=[], help="Bitbucket repositories to inspect")
    parser.add_argument("--branches", nargs="*", help="Branches to include")
    parser.add_argument("--develop-only", action="store_true", help="Shortcut for using the develop branch only")
    parser.add_argument("--freeze-date", help="ISO formatted freeze date (YYYY-MM-DD)")
    parser.add_argument("--window-days", type=int, default=28, help="Days before freeze date to include commits")
    parser.add_argument("--use-cache", action="store_true", help="Reuse cached API responses where available")
    parser.add_argument("--upload-s3", action="store_true", help="Upload outputs to Amazon S3")
    parser.add_argument("--s3-bucket", help="Override the default S3 bucket")
    parser.add_argument("--s3-prefix", help="Override the default S3 prefix")
    parser.add_argument("--output-prefix", default="audit_results", help="Basename for output files")

    args = parser.parse_args(argv)

    return AuditConfig(
        fix_version=args.fix_version,
        repos=args.repos,
        branches=args.branches,
        window_days=args.window_days,
        freeze_date=args.freeze_date,
        develop_only=args.develop_only,
        upload_s3=args.upload_s3,
        use_cache=args.use_cache,
        s3_bucket=args.s3_bucket,
        s3_prefix=args.s3_prefix,
        output_prefix=args.output_prefix,
    )


def run_audit(config: AuditConfig) -> Dict[str, Any]:
    setup_logging()
    logger = logging.getLogger(__name__)

    settings = load_settings()
    region = settings.get("aws", {}).get("region")
    secrets_manager = SecretsManager(region_name=region)
    credential_store = CredentialStore(secrets_manager=secrets_manager)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    jira_client = build_jira_client(settings, credential_store)
    bitbucket_client = build_bitbucket_client(settings, credential_store)

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

    issues, jira_cache_path = jira_client.fetch_issues(
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

    # Collect raw payload cache files for optional S3 upload
    raw_files: List[Path] = [path for path in [jira_cache_path] if path]
    for cache_key in cache_keys:
        cache_file = bitbucket_client.get_last_cache_file(cache_key)
        if cache_file:
            raw_files.append(cache_file)

    if config.upload_s3:
        upload_artifacts(
            config=config,
            settings=settings,
            artifacts=[Path(p) for p in artifacts.values()],
            raw_files=raw_files,
            region=region,
        )

    logger.info("Audit finished", extra={"summary": audit_result.summary})
    return {"summary": audit_result.summary, "artifacts": artifacts}


def build_jira_client(settings: Dict[str, Any], credential_store: CredentialStore) -> JiraClient:
    jira_cfg = settings.get("jira", {})
    aws_cfg = settings.get("aws", {})
    secret_id = (
        aws_cfg.get("secrets", {}).get("jira")
        or os.getenv("JIRA_SECRET_ARN")
        or os.getenv("OAUTH_SECRET_ARN")
    )

    base_url = credential_store.get(
        "JIRA_BASE_URL",
        secret_id=secret_id,
        default=jira_cfg.get("base_url"),
    )
    if not base_url:
        raise RuntimeError("Jira base URL is not configured")

    token_expiry_raw = credential_store.get("JIRA_TOKEN_EXPIRY", secret_id=secret_id)
    token_expiry = int(token_expiry_raw) if token_expiry_raw else None

    return JiraClient(
        base_url=base_url,
        client_id=credential_store.get("JIRA_CLIENT_ID", secret_id=secret_id),
        client_secret=credential_store.get("JIRA_CLIENT_SECRET", secret_id=secret_id),
        access_token=credential_store.get("JIRA_ACCESS_TOKEN", secret_id=secret_id),
        refresh_token=credential_store.get("JIRA_REFRESH_TOKEN", secret_id=secret_id),
        token_expiry=token_expiry,
        cache_dir=TEMP_DIR / "jira",
    )


def build_bitbucket_client(settings: Dict[str, Any], credential_store: CredentialStore) -> BitbucketClient:
    bitbucket_cfg = settings.get("bitbucket", {})
    aws_cfg = settings.get("aws", {})
    secret_id = (
        aws_cfg.get("secrets", {}).get("bitbucket")
        or os.getenv("BITBUCKET_SECRET_ARN")
        or os.getenv("OAUTH_SECRET_ARN")
    )

    workspace = credential_store.get(
        "BITBUCKET_WORKSPACE",
        secret_id=secret_id,
        default=bitbucket_cfg.get("workspace"),
    )
    if not workspace:
        raise RuntimeError("Bitbucket workspace is not configured")

    return BitbucketClient(
        workspace=workspace,
        username=credential_store.get("BITBUCKET_USERNAME", secret_id=secret_id),
        app_password=credential_store.get("BITBUCKET_APP_PASSWORD", secret_id=secret_id),
        access_token=credential_store.get("BITBUCKET_ACCESS_TOKEN", secret_id=secret_id),
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
    artifacts: Iterable[Path],
    raw_files: Iterable[Path],
    region: Optional[str],
) -> None:
    bucket = (
        config.s3_bucket
        or settings.get("aws", {}).get("s3_bucket")
        or os.getenv("ARTIFACTS_BUCKET")
    )
    if not bucket:
        raise RuntimeError("S3 bucket is required for uploads")
    prefix_root = config.s3_prefix or settings.get("aws", {}).get("s3_prefix", "")
    prefix = "/".join(filter(None, [prefix_root.rstrip("/"), config.fix_version]))

    to_upload = list(artifacts)
    to_upload.extend(raw_files)

    s3_utils.upload_files(bucket=bucket, prefix=prefix, files=to_upload, region_name=region)


if __name__ == "__main__":
    config = parse_args()
    run_audit(config)

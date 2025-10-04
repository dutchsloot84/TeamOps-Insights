"""Shared configuration helpers used across the CLI and Lambda entry points."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

import yaml

__all__ = [
    "Defaults",
    "load_defaults",
    "load_config",
    "get_aws_region",
    "get_s3_destination",
    "get_dynamodb_table",
    "get_secrets_mapping",
]

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SETTINGS_PATH = REPO_ROOT / "config" / "settings.yaml"


@dataclass(frozen=True)
class Defaults:
    """Container for common filesystem defaults used by the CLI and Lambda."""

    project_root: Path
    cache_dir: Path
    artifact_dir: Path
    reports_dir: Path
    settings_path: Path
    export_formats: tuple[str, ...]

    def as_dict(self) -> dict[str, str]:
        """Return a serialisable mapping of default paths for introspection."""

        return {
            "project_root": str(self.project_root),
            "cache_dir": str(self.cache_dir),
            "artifact_dir": str(self.artifact_dir),
            "reports_dir": str(self.reports_dir),
            "settings_path": str(self.settings_path),
            "export_formats": ",".join(self.export_formats),
        }


def _env(env: Mapping[str, str], key: str, default: str) -> str:
    value = env.get(key)
    return value if value else default


def _load_settings_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    if suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    raise ValueError(f"Unsupported configuration format: {path}")


def load_config(path: Optional[str | Path] = None) -> Dict[str, Any]:
    """Load configuration data from ``path`` or the default settings file."""

    target = Path(path) if path is not None else DEFAULT_SETTINGS_PATH
    return _load_settings_file(target)


def get_aws_region(config: Mapping[str, Any], env: Mapping[str, str] | None = None) -> str | None:
    """Return the AWS region derived from configuration or environment."""

    env = env or os.environ
    aws_config = config.get("aws", {}) if isinstance(config, Mapping) else {}
    region = aws_config.get("region") if isinstance(aws_config, Mapping) else None
    if region:
        return str(region)
    for key in ("AWS_REGION", "AWS_DEFAULT_REGION"):
        if env.get(key):
            return env[key]
    return None


def get_s3_destination(config: Mapping[str, Any]) -> Tuple[str | None, str | None]:
    """Return the S3 bucket and prefix configured for artifacts."""

    aws_config = config.get("aws", {}) if isinstance(config, Mapping) else {}
    bucket = None
    prefix = None
    if isinstance(aws_config, Mapping):
        bucket_value = aws_config.get("s3_bucket")
        prefix_value = aws_config.get("s3_prefix")
        bucket = str(bucket_value) if bucket_value else None
        prefix = str(prefix_value) if prefix_value else None
    return bucket, prefix


def get_dynamodb_table(config: Mapping[str, Any]) -> str | None:
    """Return the DynamoDB table name used for Jira webhook caches."""

    jira_cfg = config.get("jira", {}) if isinstance(config, Mapping) else {}
    if isinstance(jira_cfg, Mapping):
        table_name = jira_cfg.get("issue_table_name")
        return str(table_name) if table_name else None
    return None


def get_secrets_mapping(config: Mapping[str, Any]) -> Dict[str, str]:
    """Return the configured Secrets Manager identifiers keyed by logical name."""

    aws_config = config.get("aws", {}) if isinstance(config, Mapping) else {}
    secrets = aws_config.get("secrets", {}) if isinstance(aws_config, Mapping) else {}
    if not isinstance(secrets, Mapping):
        return {}
    resolved: Dict[str, str] = {}
    for key, value in secrets.items():
        if not isinstance(key, str) or not value:
            continue
        resolved[key] = str(value)
    return resolved


def load_defaults(env: Mapping[str, str] | None = None) -> Defaults:
    """Compute default directories and configuration paths.

    Environment overrides allow hosted environments (for example Lambda) to
    tailor directory layouts without modifying the CLI logic. Every path is
    resolved to an absolute location to avoid surprises with relative working
    directories.
    """

    env = env or os.environ
    project_root = Path(_env(env, "RC_ROOT", str(Path(__file__).resolve().parents[2]))).resolve()
    cache_dir = Path(_env(env, "RC_CACHE_DIR", str(project_root / "temp_data"))).resolve()
    artifact_dir = Path(_env(env, "RC_ARTIFACT_DIR", str(project_root / "dist"))).resolve()
    reports_dir = Path(_env(env, "RC_REPORTS_DIR", str(project_root / "reports"))).resolve()
    settings_path = Path(_env(env, "RC_SETTINGS_FILE", str(project_root / "config" / "settings.yaml"))).resolve()
    export_formats = tuple(
        fmt.strip()
        for fmt in _env(env, "RC_EXPORT_FORMATS", "json,excel").split(",")
        if fmt.strip()
    )
    if not export_formats:
        export_formats = ("json", "excel")
    return Defaults(
        project_root=project_root,
        cache_dir=cache_dir,
        artifact_dir=artifact_dir,
        reports_dir=reports_dir,
        settings_path=settings_path,
        export_formats=export_formats,
    )

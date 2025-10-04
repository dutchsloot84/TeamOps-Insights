"""Shared configuration helpers used across the CLI and Lambda entry points."""

from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, MutableMapping, Sequence, Tuple

import yaml

from clients.secrets_manager import CredentialStore, SecretsManager

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
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "defaults.yml"
DEFAULT_OVERRIDE_PATH = REPO_ROOT / "config" / "settings.yaml"


class ConfigurationError(RuntimeError):
    """Raised when configuration validation fails."""


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


def get_aws_region(
    config: Mapping[str, Any], env: Mapping[str, str] | None = None
) -> str | None:
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

    storage_cfg = config.get("storage", {}) if isinstance(config, Mapping) else {}
    if isinstance(storage_cfg, Mapping):
        dynamodb_cfg = storage_cfg.get("dynamodb", {}) if isinstance(storage_cfg, Mapping) else {}
        if isinstance(dynamodb_cfg, Mapping):
            table_name = dynamodb_cfg.get("jira_issue_table")
            if table_name:
                return str(table_name)

    # Fallback to legacy location for backwards compatibility
    jira_cfg = config.get("jira", {}) if isinstance(config, Mapping) else {}
    if isinstance(jira_cfg, Mapping):
        legacy = jira_cfg.get("issue_table_name")
        return str(legacy) if legacy else None
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
    project_root = Path(
        _env(env, "RC_ROOT", str(Path(__file__).resolve().parents[2]))
    ).resolve()
    cache_dir = Path(
        _env(env, "RC_CACHE_DIR", str(project_root / "temp_data"))
    ).resolve()
    artifact_dir = Path(
        _env(env, "RC_ARTIFACT_DIR", str(project_root / "dist"))
    ).resolve()
    reports_dir = Path(
        _env(env, "RC_REPORTS_DIR", str(project_root / "reports"))
    ).resolve()
    settings_path = Path(
        _env(env, "RC_SETTINGS_FILE", str(project_root / "config" / "defaults.yml"))
    ).resolve()
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


_ENVIRONMENT_PATHS: dict[str, Sequence[str]] = {
    "AWS_REGION": ("aws", "region"),
    "ARTIFACTS_BUCKET": ("storage", "s3", "bucket"),
    "ARTIFACTS_PREFIX": ("storage", "s3", "prefix"),
    "JIRA_BASE_URL": ("jira", "base_url"),
    "JIRA_CLOUD_ID": ("jira", "cloud_id"),
    "JIRA_SCOPE_PROJECT": ("jira", "scopes", "project"),
    "JIRA_SCOPE_FIXVERSION": ("jira", "scopes", "fixVersion"),
    "JIRA_SCOPE_JQL": ("jira", "scopes", "jql"),
    "JIRA_ISSUE_TABLE": ("storage", "dynamodb", "jira_issue_table"),
    "BITBUCKET_WORKSPACE": ("bitbucket", "workspace"),
    "BITBUCKET_REPOSITORIES": ("bitbucket", "repositories"),
    "BITBUCKET_DEFAULT_BRANCHES": ("bitbucket", "default_branches"),
    "BITBUCKET_USERNAME": ("bitbucket", "credentials", "username"),
    "BITBUCKET_APP_PASSWORD": ("bitbucket", "credentials", "app_password"),
    "BITBUCKET_ACCESS_TOKEN": ("bitbucket", "credentials", "access_token"),
    "JIRA_CLIENT_ID": ("jira", "credentials", "client_id"),
    "JIRA_CLIENT_SECRET": ("jira", "credentials", "client_secret"),
    "JIRA_ACCESS_TOKEN": ("jira", "credentials", "access_token"),
    "JIRA_REFRESH_TOKEN": ("jira", "credentials", "refresh_token"),
    "JIRA_TOKEN_EXPIRY": ("jira", "credentials", "token_expiry"),
    "WEBHOOK_SECRET": ("webhooks", "jira", "secret"),
    "JIRA_SECRET_ARN": ("secrets", "jira_oauth", "arn"),
    "BITBUCKET_SECRET_ARN": ("secrets", "bitbucket_token", "arn"),
    "WEBHOOK_SECRET_ARN": ("secrets", "webhook_secret", "arn"),
    "OAUTH_SECRET_ARN": ("secrets", "jira_oauth", "arn"),
}

_LIST_ENV_KEYS = {"BITBUCKET_REPOSITORIES", "BITBUCKET_DEFAULT_BRANCHES"}
_INT_ENV_KEYS = {"JIRA_TOKEN_EXPIRY"}


_REQUIRED_PATHS: dict[tuple[str, ...], type] = {
    ("aws", "region"): str,
    ("storage", "s3", "bucket"): str,
    ("storage", "s3", "prefix"): str,
    ("storage", "dynamodb", "jira_issue_table"): str,
    ("jira", "base_url"): str,
    ("jira", "scopes", "project"): str,
    ("jira", "scopes", "fixVersion"): str,
    ("jira", "scopes", "jql"): str,
    ("bitbucket", "workspace"): str,
    ("secrets", "jira_oauth", "arn"): str,
    ("secrets", "bitbucket_token", "arn"): str,
    ("secrets", "webhook_secret", "arn"): str,
}


def _ensure_mapping(value: Any) -> MutableMapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigurationError("Configuration data must be a mapping at every level.")
    return dict(value)


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = _deep_merge(_ensure_mapping(result[key]), value)
        else:
            result[key] = value
    return result


def _set_path(
    config: MutableMapping[str, Any], path: Sequence[str], value: Any
) -> None:
    cursor: MutableMapping[str, Any] = config
    for segment in path[:-1]:
        existing = cursor.get(segment)
        if not isinstance(existing, Mapping):
            existing = {}
        cursor[segment] = dict(existing)
        cursor = cursor[segment]  # type: ignore[assignment]
    cursor[path[-1]] = value


def _get_path(config: Mapping[str, Any], path: Sequence[str]) -> Any:
    cursor: Any = config
    for segment in path:
        if not isinstance(cursor, Mapping):
            return None
        cursor = cursor.get(segment)
    return cursor


def _parse_env_value(key: str, value: str) -> Any:
    if key in _LIST_ENV_KEYS:
        return [item.strip() for item in value.split(",") if item.strip()]
    if key in _INT_ENV_KEYS:
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ConfigurationError(f"Environment variable {key} must be an integer.")
    lowered = value.lower().strip()
    if lowered in {"true", "1", "yes", "on"}:
        return True
    if lowered in {"false", "0", "no", "off"}:
        return False
    return value


def _apply_environment_overrides(
    config: MutableMapping[str, Any], env: Mapping[str, str]
) -> None:
    for env_key, path in _ENVIRONMENT_PATHS.items():
        if env_key not in env:
            continue
        value = _parse_env_value(env_key, env[env_key])
        _set_path(config, path, value)


def _apply_secret_overrides(
    config: MutableMapping[str, Any],
    credential_store: CredentialStore,
) -> None:
    secrets_cfg = config.get("secrets")
    if not isinstance(secrets_cfg, Mapping):
        return
    for secret_name, metadata in secrets_cfg.items():
        if not isinstance(metadata, Mapping):
            continue
        arn = metadata.get("arn")
        if not arn:
            continue
        payload = credential_store.get_all_from_secret(arn)
        if not payload:
            continue
        values_map = metadata.get("values") or {}
        if not isinstance(values_map, Mapping):
            continue
        for path_str, key in values_map.items():
            if not isinstance(path_str, str) or not key:
                continue
            if key not in payload:
                continue
            path = tuple(path_str.split("."))
            _set_path(config, path, payload[key])


def _validate_schema(config: Mapping[str, Any]) -> None:
    missing: list[str] = []
    for path, expected_type in _REQUIRED_PATHS.items():
        value = _get_path(config, path)
        if value in (None, ""):
            missing.append(".".join(path))
            continue
        if not isinstance(value, expected_type):
            raise ConfigurationError(
                f"Configuration value {'.'.join(path)} must be of type {expected_type.__name__}."
            )
    if missing:
        raise ConfigurationError(
            "Missing required configuration values: " + ", ".join(sorted(missing))
        )


def load_config(
    path: str | os.PathLike | None = None,
    *,
    overrides: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
    defaults_path: Path | None = None,
    override_path: Path | None = None,
    credential_store: CredentialStore | None = None,
) -> Dict[str, Any]:
    """Load the layered configuration with deterministic precedence."""

    if path is not None and override_path is None:
        override_path = Path(path)

    defaults_file = defaults_path or DEFAULT_CONFIG_PATH
    with defaults_file.open("r", encoding="utf-8") as handle:
        raw_defaults = yaml.safe_load(handle) or {}
    if not isinstance(raw_defaults, Mapping):
        raise ConfigurationError("defaults.yml must contain a mapping at the top level")

    config: MutableMapping[str, Any] = dict(copy.deepcopy(raw_defaults))

    region = _get_path(config, ("aws", "region"))
    secrets_manager = credential_store
    if secrets_manager is None:
        sm_client = SecretsManager(
            region_name=region if isinstance(region, str) else None
        )
        secrets_manager = CredentialStore(secrets_manager=sm_client)

    _apply_secret_overrides(config, secrets_manager)

    env_map = env or os.environ
    _apply_environment_overrides(config, env_map)

    file_overrides: Mapping[str, Any] = {}
    override_file = override_path or DEFAULT_OVERRIDE_PATH
    if override_file and Path(override_file).exists():
        file_overrides = _load_settings_file(Path(override_file))
        if file_overrides:
            config = _deep_merge(config, file_overrides)

    if overrides:
        config = _deep_merge(config, overrides)

    _validate_schema(config)
    return dict(config)

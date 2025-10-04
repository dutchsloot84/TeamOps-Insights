"""Shared configuration helpers used across the CLI and Lambda entry points."""
from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, MutableMapping, Optional, Sequence, Tuple

import yaml

from clients.secrets_manager import CredentialStore, SecretsManager

__all__ = [
    "Defaults",
    "load_defaults",
    "load_config",
    "ConfigurationError",
    "get_aws_region",
    "get_s3_destination",
    "get_dynamodb_table",
    "get_secrets_mapping",
]

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "defaults.yml"
DEFAULT_OVERRIDE_PATH = REPO_ROOT / "config" / "settings.yaml"


class ConfigurationError(RuntimeError):
    """Raised when configuration parsing fails."""


def _env(env: Mapping[str, str], key: str, default: str) -> str:
    value = env.get(key)
    return value if value else default


def _load_settings_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    elif suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        raise ConfigurationError(f"Unsupported configuration format: {path}")

    if not isinstance(data, Mapping):
        raise ConfigurationError(
            f"Configuration file {path} must contain a top-level mapping."
        )
    return dict(data)


def _ensure_mutable_mapping(value: Any) -> MutableMapping[str, Any]:
    if isinstance(value, MutableMapping):
        return value
    return {}


def _assign_path(target: MutableMapping[str, Any], path: Sequence[str], value: Any) -> None:
    cursor: MutableMapping[str, Any] = target
    for part in path[:-1]:
        existing = cursor.get(part)
        if not isinstance(existing, MutableMapping):
            existing = {}
            cursor[part] = existing
        cursor = existing
    cursor[path[-1]] = value


def _deep_merge(base: MutableMapping[str, Any], updates: Mapping[str, Any]) -> MutableMapping[str, Any]:
    for key, value in updates.items():
        if isinstance(value, Mapping):
            existing = base.get(key)
            if isinstance(existing, MutableMapping):
                base[key] = _deep_merge(existing, value)
            else:
                base[key] = _deep_merge({}, value)
        elif isinstance(value, list):
            base[key] = list(value)
        else:
            base[key] = value
    return base


_ENVIRONMENT_MAPPINGS: Dict[str, Sequence[str]] = {
    "RC_S3_BUCKET": ("aws", "s3_bucket"),
    "RC_S3_PREFIX": ("aws", "s3_prefix"),
    "RC_REGION": ("aws", "region"),
    "AWS_REGION": ("aws", "region"),
    "AWS_DEFAULT_REGION": ("aws", "region"),
    "WEBHOOK_SECRET_ARN": ("aws", "secrets", "webhook"),
    "JIRA_SECRET_ARN": ("aws", "secrets", "jira"),
    "BITBUCKET_SECRET_ARN": ("aws", "secrets", "bitbucket"),
}


def _environment_overrides(env: Mapping[str, str]) -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}
    for key, path in _ENVIRONMENT_MAPPINGS.items():
        value = env.get(key)
        if value is None:
            continue
        _assign_path(overrides, path, value)
    return overrides


def _boolean_from_env(env: Mapping[str, str], *keys: str) -> Optional[bool]:
    truthy = {"1", "true", "yes", "on", "y", "t"}
    falsy = {"0", "false", "no", "off", "n", "f"}
    for key in keys:
        raw = env.get(key)
        if raw is None:
            continue
        lowered = raw.strip().lower()
        if lowered in truthy:
            return True
        if lowered in falsy:
            return False
    return None


def _should_use_secrets_manager(config: Mapping[str, Any], env: Mapping[str, str]) -> bool:
    env_override = _boolean_from_env(env, "RC_USE_AWS_SECRETS_MANAGER", "USE_AWS_SECRETS_MANAGER")
    if env_override is not None:
        return env_override

    aws_cfg = config.get("aws", {}) if isinstance(config, Mapping) else {}
    if isinstance(aws_cfg, Mapping):
        value = aws_cfg.get("use_secrets_manager")
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            parsed = _boolean_from_env({"value": value}, "value")
            if parsed is not None:
                return parsed
    return False


def _load_secret_payloads(config: MutableMapping[str, Any], store: CredentialStore) -> None:
    secrets_map = get_secrets_mapping(config)
    if not secrets_map:
        return

    payloads: Dict[str, Any] = {}
    for name, secret_id in secrets_map.items():
        payload = store.get_all_from_secret(secret_id)
        if payload:
            payloads[name] = payload

    if not payloads:
        return

    aws_cfg = _ensure_mutable_mapping(config.get("aws"))
    existing = aws_cfg.get("secrets_payloads")
    if isinstance(existing, MutableMapping):
        existing.update(payloads)
    else:
        aws_cfg["secrets_payloads"] = payloads
    config["aws"] = aws_cfg


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


def load_defaults(env: Mapping[str, str] | None = None) -> Defaults:
    """Compute default directories and configuration paths.

    Environment overrides allow hosted environments (for example Lambda) to
    tailor directory layouts without modifying the CLI logic. Every path is
    resolved to an absolute location to avoid surprises with relative working
    directories.
    """

    env = env or os.environ
    project_root = Path(_env(env, "RC_ROOT", str(REPO_ROOT))).resolve()
    cache_dir = Path(_env(env, "RC_CACHE_DIR", str(project_root / "temp_data"))).resolve()
    artifact_dir = Path(_env(env, "RC_ARTIFACT_DIR", str(project_root / "dist"))).resolve()
    reports_dir = Path(_env(env, "RC_REPORTS_DIR", str(project_root / "reports"))).resolve()
    settings_path = Path(_env(env, "RC_SETTINGS_FILE", str(DEFAULT_OVERRIDE_PATH))).resolve()
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


def get_aws_region(config: Mapping[str, Any], env: Mapping[str, str] | None = None) -> str | None:
    """Return the AWS region derived from configuration or environment."""

    env = env or os.environ
    aws_config = config.get("aws", {}) if isinstance(config, Mapping) else {}
    region = aws_config.get("region") if isinstance(aws_config, Mapping) else None
    if region:
        return str(region)
    for key in ("RC_REGION", "AWS_REGION", "AWS_DEFAULT_REGION"):
        if env.get(key):
            return env[key]
    return None


def load_config(
    path: Optional[str | Path] = None,
    *,
    defaults_path: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    secrets_manager: SecretsManager | None = None,
    credential_store: CredentialStore | None = None,
) -> Dict[str, Any]:
    """Load layered configuration from defaults, overrides, environment, and secrets."""

    env = env or os.environ
    config: MutableMapping[str, Any] = {}

    defaults_target = Path(defaults_path) if defaults_path else DEFAULT_CONFIG_PATH
    defaults_data = _load_settings_file(defaults_target)
    config = _deep_merge(config, defaults_data)

    override_target = Path(path) if path is not None else DEFAULT_OVERRIDE_PATH
    override_data = _load_settings_file(override_target)
    config = _deep_merge(config, override_data)

    env_overrides = _environment_overrides(env)
    config = _deep_merge(config, env_overrides)

    if _should_use_secrets_manager(config, env):
        store = credential_store
        if store is None:
            manager = secrets_manager
            if manager is None:
                region = get_aws_region(config, env)
                manager = SecretsManager(region_name=region)
            store = CredentialStore(secrets_manager=manager)
        _load_secret_payloads(config, store)

    return deepcopy(dict(config))


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


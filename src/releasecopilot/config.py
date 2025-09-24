"""Configuration helpers for Release Copilot."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Dict, Iterable

import yaml

from . import aws_secrets

# Keys that the configuration system understands by default. Additional keys
# discovered in the YAML file will also be considered for environment
# overrides.
KNOWN_CONFIG_KEYS: set[str] = {
    "bitbucket_base",
    "bitbucket_token",
    "fix_version",
    "jira_base",
    "jira_token",
    "jira_user",
    "s3_bucket",
    "s3_prefix",
    "use_aws_secrets_manager",
}

# Keys that should be interpreted as booleans when sourced from the
# environment.
BOOLEAN_KEYS = {"use_aws_secrets_manager"}

# Common prefixes that may be used for environment variables. The empty string
# allows direct lookups (e.g. ``JIRA_TOKEN``) while the others support names
# like ``RELEASECOPILOT_JIRA_TOKEN``.
ENV_PREFIXES = ("", "RELEASECOPILOT_", "RELEASE_COPILOT_")


class ConfigError(RuntimeError):
    """Raised when configuration validation fails."""


def load_yaml_defaults(path: str | Path | None) -> dict:
    """Load YAML configuration defaults from ``path``.

    If the file is missing, an empty dictionary is returned.

    Parameters
    ----------
    path:
        Path to the YAML file. ``None`` is treated as a missing file.

    Returns
    -------
    dict
        Parsed YAML data or ``{}`` if the file does not exist.
    """

    if not path:
        return {}

    yaml_path = Path(path)
    if not yaml_path.exists():
        return {}

    with yaml_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    if not isinstance(data, dict):
        raise ConfigError(
            f"Expected top-level mapping in configuration file '{yaml_path}',"
            f" but received {type(data).__name__}."
        )

    return data


def _coerce_bool(value: str) -> bool:
    truthy = {"1", "true", "yes", "on", "y", "t"}
    falsy = {"0", "false", "no", "off", "n", "f"}
    lowered = value.strip().lower()
    if lowered in truthy:
        return True
    if lowered in falsy:
        return False
    raise ConfigError(f"Unable to interpret boolean value from '{value}'.")


def load_env_overrides(keys: Iterable[str]) -> dict:
    """Return environment overrides for ``keys``.

    Environment lookups are case insensitive and support optional
    ``RELEASECOPILOT_`` / ``RELEASE_COPILOT_`` prefixes. Values for keys
    registered in :data:`BOOLEAN_KEYS` are parsed into booleans.
    """

    overrides: Dict[str, Any] = {}
    for key in keys:
        candidates = [key, key.upper()]
        env_value = None
        for candidate in candidates:
            for prefix in ENV_PREFIXES:
                env_key = f"{prefix}{candidate.upper()}"
                if env_key in os.environ:
                    env_value = os.environ[env_key]
                    break
            if env_value is not None:
                break
        if env_value is None:
            continue

        if key in BOOLEAN_KEYS:
            overrides[key] = _coerce_bool(env_value)
        else:
            overrides[key] = env_value

    return overrides


def merge_configs(*dicts: Dict[str, Any]) -> dict:
    """Merge dictionaries honoring precedence from left to right."""

    merged: Dict[str, Any] = {}
    for cfg in reversed(dicts):
        if not cfg:
            continue
        merged.update(cfg)
    return merged


def resolve_secret(name: str, cfg: Dict[str, Any]) -> str | None:
    """Resolve ``name`` within ``cfg`` respecting secret precedence."""

    if not name:
        raise ValueError("Secret name must be provided.")
    if cfg is None:
        raise ValueError("Configuration dictionary is required.")

    for candidate in (name, name.lower(), name.upper()):
        value = cfg.get(candidate)
        if value:
            return value

    secrets = cfg.get("secrets")
    if isinstance(secrets, dict):
        for candidate in (name, name.lower(), name.upper()):
            value = secrets.get(candidate)
            if value:
                cfg[name] = value
                return value

    if cfg.get("use_aws_secrets_manager"):
        secret = aws_secrets.get_secret(name)
        if secret:
            cfg[name] = secret
            return secret

    return None


def _extract_cli_overrides(cli_args: argparse.Namespace) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    for key, value in vars(cli_args).items():
        if key in {"config", "log_level"}:
            continue
        if value is None:
            continue
        data[key] = value
    return data


def build_config(cli_args: argparse.Namespace) -> dict:
    """Build the final configuration dictionary from CLI, env, and YAML."""

    if not isinstance(cli_args, argparse.Namespace):
        raise TypeError("cli_args must be an argparse.Namespace instance")

    config_path: Path | None = None
    if getattr(cli_args, "config", None):
        config_path = Path(cli_args.config)
        if not config_path.exists():
            raise ConfigError(f"Configuration file '{config_path}' was not found.")
    else:
        default_path = Path("releasecopilot.yaml")
        if default_path.exists():
            config_path = default_path

    yaml_defaults = load_yaml_defaults(config_path)

    env_keys = set(KNOWN_CONFIG_KEYS)
    env_keys.update(key for key in yaml_defaults.keys() if isinstance(key, str))
    secrets_block = yaml_defaults.get("secrets")
    if isinstance(secrets_block, dict):
        env_keys.update(key for key in secrets_block.keys() if isinstance(key, str))

    env_overrides = load_env_overrides(env_keys)
    cli_overrides = _extract_cli_overrides(cli_args)

    merged = merge_configs(cli_overrides, env_overrides, yaml_defaults)
    if config_path:
        merged["config_path"] = str(config_path)

    merged["use_aws_secrets_manager"] = bool(merged.get("use_aws_secrets_manager"))

    for secret_name in ("jira_token", "bitbucket_token"):
        resolve_secret(secret_name, merged)

    required_fields = ("fix_version", "jira_base", "bitbucket_base")
    missing = [field for field in required_fields if not merged.get(field)]
    if missing:
        raise ConfigError(
            "Missing required configuration values: " + ", ".join(sorted(missing))
        )

    return merged

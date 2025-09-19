#!/usr/bin/env python3
"""Bootstrap and deploy the audit CDK stacks for a given environment."""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


LOGGER = logging.getLogger("deploy_env")


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return False


def _load_env_config(env_name: str) -> Dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    env_dir = root / "infra" / "envs"
    candidates = [env_dir / f"{env_name}{suffix}" for suffix in (".json", ".yaml", ".yml")]

    for path in candidates:
        if not path.exists():
            continue
        LOGGER.info("Loading environment configuration from %s", path)
        if path.suffix == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
        try:
            import yaml  # type: ignore
        except ImportError as exc:  # pragma: no cover - defensive branch
            raise RuntimeError(
                "PyYAML is required to parse YAML environment files. Install it via `pip install PyYAML`."
            ) from exc
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    raise FileNotFoundError(
        f"No configuration file found for environment '{env_name}'. Expected one of: "
        + ", ".join(str(path) for path in candidates)
    )


def _normalise_context(config: Dict[str, Any], env_override: str, disable_schedule: bool) -> Dict[str, Any]:
    context: Dict[str, Any] = {}
    context["env"] = config.get("env", env_override)
    context["project"] = config.get("project", "releasecopilot")
    context["region"] = config.get("region", os.getenv("CDK_DEFAULT_REGION", "us-west-2"))
    context["bucketBase"] = config.get("bucketBase")
    context["reportPrefix"] = config.get("reportPrefix", "reports/")
    context["rawPrefix"] = config.get("rawPrefix", "raw/")
    context["logLevel"] = config.get("logLevel", "INFO")
    context["lambdaModule"] = config.get("lambdaModule", "aws.core_handler")
    context["retainBucket"] = _as_bool(config.get("retainBucket", context["env"] == "prod"))
    context["scheduleCron"] = config.get("scheduleCron", "cron(30 8 * * ? *)")

    secrets = config.get("secrets", {})
    if not isinstance(secrets, dict):
        raise ValueError("`secrets` must be an object mapping logical names to secret names")
    context["secrets"] = secrets

    schedule_enabled = _as_bool(config.get("scheduleEnabled", False))
    if disable_schedule:
        schedule_enabled = False
    context["scheduleEnabled"] = schedule_enabled

    fix_version = config.get("fixVersion")
    if fix_version is not None:
        context["fixVersion"] = fix_version

    return context


def _format_context_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


def _run(cmd: list[str], *, cwd: Path, env: Dict[str, str]) -> None:
    LOGGER.info("Running: %s", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def _package_lambda(root: Path) -> None:
    package_script = root / "scripts" / "package_lambda.sh"
    if not package_script.exists():
        raise FileNotFoundError(f"Packaging script not found at {package_script}")
    _run(["bash", str(package_script)], cwd=root, env=os.environ.copy())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy the audit CDK stacks for an environment")
    parser.add_argument("--env", required=True, help="Environment identifier (matches file name under infra/envs)")
    parser.add_argument(
        "--package",
        action="store_true",
        help="Invoke scripts/package_lambda.sh before deploying",
    )
    parser.add_argument(
        "--no-schedule",
        action="store_true",
        help="Force-disable the EventBridge schedule regardless of config",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()

    try:
        config = _load_env_config(args.env)
        context = _normalise_context(config, args.env, args.no_schedule)
    except Exception as exc:  # pragma: no cover - initialization failures
        LOGGER.error("Failed to load environment configuration: %s", exc)
        return 1

    root = Path(__file__).resolve().parents[1]
    cdk_dir = root / "infra" / "cdk"

    if context.get("bucketBase") in (None, ""):
        LOGGER.error("Environment configuration must define `bucketBase`.")
        return 1

    env_vars = os.environ.copy()
    region = str(context["region"])
    env_vars.setdefault("CDK_DEFAULT_REGION", region)
    env_vars.setdefault("AWS_DEFAULT_REGION", region)

    context_args: list[str] = []
    for key, value in context.items():
        context_args.extend(["-c", f"{key}={_format_context_value(value)}"])

    try:
        if args.package:
            LOGGER.info("Packaging Lambda artifact")
            _package_lambda(root)

        LOGGER.info("Bootstrapping environment (if required)")
        _run(["cdk", "bootstrap", *context_args], cwd=cdk_dir, env=env_vars)

        LOGGER.info("Deploying CDK stacks")
        _run(
            ["cdk", "deploy", "--require-approval", "never", *context_args],
            cwd=cdk_dir,
            env=env_vars,
        )
    except subprocess.CalledProcessError as exc:
        LOGGER.error("Command failed with exit code %s", exc.returncode)
        return exc.returncode
    except FileNotFoundError as exc:
        LOGGER.error("Required executable not found: %s", exc)
        return 1

    LOGGER.info("Deployment completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())

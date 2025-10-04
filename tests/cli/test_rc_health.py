"""Unit tests for the ``rc health`` CLI entry point."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.cli import app
from src.config.loader import load_defaults
from src.ops.health import ReadinessOptions, ReadinessReport


@pytest.fixture(name="defaults")
def _defaults_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    project_root = tmp_path
    config_dir = project_root / "config"
    config_dir.mkdir()
    settings_path = config_dir / "settings.yaml"
    settings_path.write_text(
        """
aws:
  region: us-east-1
  s3_bucket: releasecopilot-artifacts
  s3_prefix: readiness
  secrets:
    jira: secret/jira
    webhook: secret/webhook
jira:
  issue_table_name: releasecopilot-jira
""".strip(),
        encoding="utf-8",
    )

    env = {
        "RC_ROOT": str(project_root),
        "RC_CACHE_DIR": str(project_root / "cache"),
        "RC_ARTIFACT_DIR": str(project_root / "dist"),
        "RC_REPORTS_DIR": str(project_root / "reports"),
        "RC_SETTINGS_FILE": str(settings_path),
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return load_defaults(env)


def _report(overall: str = "pass", dry_run: bool = False) -> ReadinessReport:
    return ReadinessReport(
        version="health.v1",
        timestamp="2024-01-01T00:00:00Z",
        overall=overall,
        checks={
            "secrets": {"status": "pass"},
            "dynamodb": {"status": "pass"},
            "s3": {"status": "pass"},
            "webhook_secret": {"status": "pass"},
        },
        cleanup_warning=None,
        dry_run=dry_run,
    )


def test_health_readiness_prints_report(monkeypatch: pytest.MonkeyPatch, defaults, capsys):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")

    def _fake_run(options: ReadinessOptions):
        return _report()

    monkeypatch.setattr("src.cli.health.run_readiness", _fake_run)

    exit_code = app.main(["health", "--readiness"], defaults=defaults)
    assert exit_code == 0

    stdout = capsys.readouterr().out
    payload = json.loads(stdout)
    assert payload["overall"] == "pass"
    assert payload["checks"]["s3"]["status"] == "pass"


def test_health_readiness_writes_json(monkeypatch: pytest.MonkeyPatch, defaults, tmp_path: Path):
    output_path = tmp_path / "health.json"

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")

    monkeypatch.setattr("src.cli.health.run_readiness", lambda options: _report())

    exit_code = app.main(
        ["health", "--readiness", "--json", str(output_path)],
        defaults=defaults,
    )
    assert exit_code == 0
    assert output_path.exists()

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["overall"] == "pass"


def test_health_readiness_respects_overrides(monkeypatch: pytest.MonkeyPatch, defaults):
    captured: dict[str, ReadinessOptions] = {}

    def _capture(options: ReadinessOptions):
        captured["options"] = options
        return _report(dry_run=True)

    monkeypatch.setattr("src.cli.health.run_readiness", _capture)

    exit_code = app.main(
        [
            "health",
            "--readiness",
            "--bucket",
            "s3://custom/reports",
            "--table",
            "custom-table",
            "--secrets",
            "jira,external/secret",
            "--dry-run",
        ],
        defaults=defaults,
    )

    assert exit_code == 0
    options = captured["options"]
    assert options.bucket == "custom"
    assert options.prefix == "reports"
    assert options.table_name == "custom-table"
    assert options.dry_run is True
    assert options.secrets["jira"] == "secret/jira"
    assert options.secrets["external/secret"] == "external/secret"


def test_health_requires_readiness_flag(monkeypatch: pytest.MonkeyPatch, defaults, capsys):
    monkeypatch.setattr("src.cli.health.run_readiness", lambda options: _report())

    exit_code = app.main(["health"], defaults=defaults)
    assert exit_code == 1
    stderr = capsys.readouterr().err
    assert "--readiness" in stderr

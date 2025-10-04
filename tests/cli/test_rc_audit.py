"""Unit tests for the ``rc audit`` CLI entry point."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.cli import app
from src.config.loader import load_defaults


@pytest.fixture(name="defaults")
def _defaults_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    project_root = tmp_path
    cache_dir = project_root / "cache"
    cache_dir.mkdir()
    artifact_dir = project_root / "dist"
    reports_dir = project_root / "reports"
    env = {
        "RC_ROOT": str(project_root),
        "RC_CACHE_DIR": str(cache_dir),
        "RC_ARTIFACT_DIR": str(artifact_dir),
        "RC_REPORTS_DIR": str(reports_dir),
        "RC_SETTINGS_FILE": str(project_root / "config" / "settings.yaml"),
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return load_defaults(env)


def test_dry_run_outputs_plan(defaults, capsys):
    exit_code = app.main(["audit", "--dry-run"], defaults=defaults)
    assert exit_code == 0

    stdout = capsys.readouterr().out
    payload = json.loads(stdout)
    plan = payload["plan"]

    assert plan["cache_dir"] == str(defaults.cache_dir)
    assert plan["outputs"]["json"].endswith("audit.json")
    assert plan["scope"] == {}


def test_invalid_scope_entry_reports_error(defaults, capsys):
    with pytest.raises(SystemExit) as excinfo:
        app.main(["audit", "--scope", "invalid"], defaults=defaults)
    assert excinfo.value.code == 2
    stderr = capsys.readouterr().err
    assert "key=value" in stderr

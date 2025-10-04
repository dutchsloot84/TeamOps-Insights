"""End-to-end tests for the offline ``rc audit`` pipeline."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from src.cli.audit import AuditInputError, AuditOptions, run_audit
from src.config.loader import load_defaults


@pytest.fixture(name="defaults")
def _defaults(tmp_path: Path) -> tuple:
    project_root = tmp_path
    cache_dir = project_root / "cache"
    artifact_dir = project_root / "dist"
    reports_dir = project_root / "reports"
    env = {
        "RC_ROOT": str(project_root),
        "RC_CACHE_DIR": str(cache_dir),
        "RC_ARTIFACT_DIR": str(artifact_dir),
        "RC_REPORTS_DIR": str(reports_dir),
        "RC_SETTINGS_FILE": str(project_root / "config" / "defaults.yml"),
    }
    defaults = load_defaults(env)
    return defaults, env


def _copy_fixture_cache(src_dir: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    for path in src_dir.iterdir():
        shutil.copy2(path, dest_dir / path.name)


def test_run_audit_generates_expected_artifacts(defaults, fixtures_dir):
    defaults_obj, env = defaults
    cache_dir = Path(env["RC_CACHE_DIR"])
    _copy_fixture_cache(fixtures_dir / "temp_data", cache_dir)

    json_path = Path(env["RC_ARTIFACT_DIR"]) / "audit.json"
    excel_path = Path(env["RC_ARTIFACT_DIR"]) / "audit.xlsx"
    summary_path = Path(env["RC_ARTIFACT_DIR"]) / "audit-summary.json"

    options = AuditOptions(
        cache_dir=cache_dir,
        json_path=json_path,
        excel_path=excel_path,
        summary_path=summary_path,
        scope={"fixVersion": "Oct25"},
        upload_uri=None,
        region=None,
        dry_run=False,
        defaults=defaults_obj,
    )

    result = run_audit(options)

    assert json_path.exists()
    assert excel_path.exists()
    assert summary_path.exists()

    golden_dir = Path(__file__).resolve().parents[1] / "fixtures" / "golden"
    generated_payload = json.loads(json_path.read_text(encoding="utf-8"))
    golden_payload = json.loads((golden_dir / "audit_results.json").read_text(encoding="utf-8"))
    assert generated_payload == golden_payload

    generated_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    golden_summary = json.loads((golden_dir / "summary.json").read_text(encoding="utf-8"))
    assert generated_summary == golden_summary

    assert result.uploaded is False
    assert result.plan["scope"] == {"fixVersion": "Oct25"}


def test_run_audit_errors_when_cache_missing(defaults):
    defaults_obj, env = defaults
    cache_dir = Path(env["RC_CACHE_DIR"])

    options = AuditOptions(
        cache_dir=cache_dir,
        json_path=Path(env["RC_ARTIFACT_DIR"]) / "audit.json",
        excel_path=Path(env["RC_ARTIFACT_DIR"]) / "audit.xlsx",
        summary_path=Path(env["RC_ARTIFACT_DIR"]) / "audit-summary.json",
        scope={},
        upload_uri=None,
        region=None,
        dry_run=False,
        defaults=defaults_obj,
    )

    with pytest.raises(AuditInputError):
        run_audit(options)

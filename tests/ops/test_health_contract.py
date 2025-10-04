"""Contract tests for readiness JSON payloads."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from src.ops.health import ReadinessClients, ReadinessOptions, run_readiness

REPO_ROOT = Path(__file__).resolve().parents[2]


def _schema() -> dict:
    schema_path = REPO_ROOT / "docs" / "schemas" / "health.v1.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


def test_example_payload_matches_schema() -> None:
    example_path = REPO_ROOT / "docs" / "examples" / "health" / "health-pass.v1.json"
    example = json.loads(example_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=example, schema=_schema())


def test_dry_run_report_matches_schema(monkeypatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    options = ReadinessOptions(
        region="us-east-1",
        bucket="bucket",
        prefix="prefix",
        table_name="table",
        secrets={"jira": "secret/jira"},
        webhook_secret_id="secret/webhook",
        webhook_env_present=False,
        dry_run=True,
        clients=ReadinessClients(secrets=None, dynamodb=None, s3=None),
    )

    report = run_readiness(options)
    jsonschema.validate(instance=report.as_dict(), schema=_schema())

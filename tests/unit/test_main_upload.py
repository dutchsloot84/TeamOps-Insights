from __future__ import annotations

import sys
import types
from datetime import datetime
from pathlib import Path

import importlib
import importlib.util

import pytest


@pytest.fixture
def main_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    root = Path(__file__).resolve().parents[2]
    root_str = str(root)
    if root_str in sys.path:
        sys.path.remove(root_str)
    sys.path.insert(0, root_str)
    src_path = root / "src"
    src_str = str(src_path)
    if src_str in sys.path:
        sys.path.remove(src_str)
    sys.path.insert(1, src_str)

    monkeypatch.delitem(sys.modules, "config", raising=False)
    monkeypatch.delitem(sys.modules, "config.settings", raising=False)
    monkeypatch.delitem(sys.modules, "main", raising=False)

    config_module = importlib.import_module("config.settings")
    sys.modules["config.settings"] = config_module

    spec = importlib.util.spec_from_file_location("main", root / "main.py")
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError("Unable to load main module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["main"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fixed_datetime(monkeypatch: pytest.MonkeyPatch, main_module: types.ModuleType) -> None:
    class FixedDatetime(datetime):
        @classmethod
        def utcnow(cls) -> "FixedDatetime":  # type: ignore[override]
            return cls(2025, 10, 24, 15, 30, 0)

    monkeypatch.setattr(main_module, "datetime", FixedDatetime)


def test_upload_artifacts_builds_versioned_prefix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    main_module: types.ModuleType,
    fixed_datetime,
) -> None:
    reports = []
    raw_files = []
    for name in ("report.json", "report.xlsx", "summary.json"):
        path = tmp_path / name
        path.write_text("data", encoding="utf-8")
        reports.append(path)
    for name in ("jira.json", "commits.json", "cache.json"):
        path = tmp_path / name
        path.write_text("data", encoding="utf-8")
        raw_files.append(path)

    temp_dir = tmp_path / "temp"
    monkeypatch.setattr(main_module, "TEMP_DIR", temp_dir)
    monkeypatch.setattr(main_module, "_detect_git_sha", lambda: "abcdef123456")

    calls: list[dict] = []

    def fake_build_client(*, region_name=None):
        return "client"

    def fake_upload_directory(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(main_module.uploader, "build_s3_client", fake_build_client)
    monkeypatch.setattr(main_module.uploader, "upload_directory", fake_upload_directory)

    config = main_module.AuditConfig(fix_version="2025.10.24", s3_bucket="bucket", s3_prefix="audits")
    settings = {"aws": {}}

    main_module.upload_artifacts(
        config=config,
        settings=settings,
        reports=reports,
        raw_files=raw_files,
        region="us-east-1",
    )

    assert len(calls) == 2

    expected_prefix = "audits/2025.10.24/2025-10-24_153000"
    assert {call["subdir"] for call in calls} == {"reports", "raw"}
    for call in calls:
        assert call["bucket"] == "bucket"
        assert call["prefix"] == expected_prefix
        assert call["client"] == "client"
        metadata = call["metadata"]
        assert metadata["fix-version"] == "2025.10.24"
        assert metadata["generated-at"] == "2025-10-24T15:30:00Z"
        assert metadata["git-sha"] == "abcdef123456"


def test_upload_artifacts_skips_when_bucket_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    main_module: types.ModuleType,
) -> None:
    monkeypatch.setattr(main_module, "TEMP_DIR", tmp_path / "temp")

    calls: list[dict] = []
    monkeypatch.setattr(main_module.uploader, "upload_directory", lambda **kwargs: calls.append(kwargs))

    config = main_module.AuditConfig(fix_version="2025.10.24")
    settings = {"aws": {}}

    main_module.upload_artifacts(
        config=config,
        settings=settings,
        reports=[],
        raw_files=[],
        region=None,
    )

    assert calls == []

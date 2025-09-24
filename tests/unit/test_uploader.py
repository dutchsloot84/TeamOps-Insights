from __future__ import annotations

from pathlib import Path

from releasecopilot import uploader


class StubS3Client:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def upload_file(self, filename: str, bucket: str, key: str, ExtraArgs: dict) -> None:  # noqa: N802 - boto3 signature
        self.calls.append(
            {
                "filename": filename,
                "bucket": bucket,
                "key": key,
                "extra_args": ExtraArgs,
            }
        )


def test_upload_directory_builds_versioned_keys(tmp_path: Path) -> None:
    base = tmp_path / "reports"
    base.mkdir()
    (base / "report.json").write_text("{}", encoding="utf-8")
    nested = base / "nested"
    nested.mkdir()
    (nested / "raw.xlsx").write_bytes(b"binary")

    client = StubS3Client()

    uploader.upload_directory(
        "my-bucket",
        "audits/2025.10.24/2025-10-24_153000",
        base,
        "reports",
        client=client,
        metadata={"fix-version": "2025.10.24"},
    )

    keys = {call["key"]: call for call in client.calls}
    assert "audits/2025.10.24/2025-10-24_153000/reports/report.json" in keys
    assert "audits/2025.10.24/2025-10-24_153000/reports/nested/raw.xlsx" in keys

    json_call = keys["audits/2025.10.24/2025-10-24_153000/reports/report.json"]
    assert json_call["extra_args"]["ServerSideEncryption"] == "AES256"
    assert json_call["extra_args"]["Metadata"]["fix-version"] == "2025.10.24"
    assert json_call["extra_args"]["ContentType"] == "application/json"


def test_upload_directory_skips_missing_directory(tmp_path: Path) -> None:
    client = StubS3Client()

    uploader.upload_directory(
        "bucket",
        "prefix",
        tmp_path / "missing",
        "reports",
        client=client,
    )

    assert client.calls == []

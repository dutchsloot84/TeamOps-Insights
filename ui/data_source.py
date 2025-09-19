"""Data source helpers for the Streamlit dashboard."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError


@dataclass(frozen=True)
class RunRef:
    """Reference to an audit run stored remotely."""

    fix_version: str
    run_date: str
    json_key: str
    excel_key: Optional[str] = None

    def label(self) -> str:
        parts = [part for part in (self.fix_version, self.run_date) if part]
        return " / ".join(parts) if parts else self.json_key


def load_local_reports(path: str | Path) -> Dict[str, Optional[Path] | Dict]:
    """Load the latest report JSON (and discover Excel) from a directory."""

    directory = Path(path).expanduser().resolve()
    if not directory.exists() or not directory.is_dir():
        raise FileNotFoundError(f"Reports directory not found: {directory}")

    json_candidates = sorted(
        directory.glob("*.json"),
        key=lambda file: file.stat().st_mtime,
        reverse=True,
    )
    if not json_candidates:
        raise FileNotFoundError(f"No JSON files found in {directory}")

    json_path = json_candidates[0]
    data = json.loads(json_path.read_text(encoding="utf-8"))

    excel_candidates = sorted(
        directory.glob("*.xlsx"),
        key=lambda file: file.stat().st_mtime,
        reverse=True,
    )
    excel_path = excel_candidates[0] if excel_candidates else None

    return {
        "data": data,
        "json_path": json_path,
        "excel_path": excel_path,
    }


def load_s3_listing(bucket: str, prefix: str = "") -> List[RunRef]:
    """List available runs in S3 grouped by fix-version and date."""

    client = boto3.client("s3")
    paginator = client.get_paginator("list_objects_v2")

    cleaned_prefix = prefix.strip("/")
    normalized_prefix = f"{cleaned_prefix}/" if cleaned_prefix else ""

    runs: Dict[tuple[str, str], Dict[str, Optional[str]]] = {}

    try:
        for page in paginator.paginate(Bucket=bucket, Prefix=normalized_prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith("/"):
                    continue
                relative = key[len(normalized_prefix) :] if normalized_prefix else key
                segments = [segment for segment in relative.split("/") if segment]
                if len(segments) < 1:
                    continue
                if len(segments) == 1:
                    fix_version = ""
                    run_date = segments[0]
                else:
                    fix_version = segments[0]
                    run_date = segments[1]
                run_key = (fix_version, run_date)
                entry = runs.setdefault(run_key, {"json": None, "excel": None})
                if key.lower().endswith(".json"):
                    entry["json"] = key
                elif key.lower().endswith((".xlsx", ".xlsm")):
                    entry["excel"] = key
    except (ClientError, BotoCoreError) as exc:  # pragma: no cover - passthrough
        raise RuntimeError(f"Unable to list objects in s3://{bucket}/{prefix}: {exc}") from exc

    run_refs = [
        RunRef(
            fix_version=fix_version,
            run_date=run_date,
            json_key=paths["json"],
            excel_key=paths.get("excel"),
        )
        for (fix_version, run_date), paths in runs.items()
        if paths.get("json")
    ]

    run_refs.sort(key=lambda ref: (ref.fix_version, ref.run_date), reverse=True)
    return run_refs


def load_s3_json(bucket: str, key: str) -> Dict:
    """Download and parse a JSON report from S3."""

    client = boto3.client("s3")
    try:
        response = client.get_object(Bucket=bucket, Key=key)
    except (ClientError, BotoCoreError) as exc:  # pragma: no cover - passthrough
        raise RuntimeError(f"Unable to download s3://{bucket}/{key}: {exc}") from exc

    body = response["Body"].read()
    return json.loads(body.decode("utf-8"))

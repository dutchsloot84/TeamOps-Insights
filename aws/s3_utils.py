"""Helper utilities for persisting artifacts to Amazon S3."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)


def upload_file(
    *,
    bucket: str,
    key: str,
    file_path: Path,
    content_type: Optional[str] = None,
    region_name: Optional[str] = None,
) -> None:
    """Upload a single file to S3."""
    try:
        client = boto3.client("s3", region_name=region_name)
        extra_args = {"ContentType": content_type} if content_type else None
        client.upload_file(str(file_path), bucket, key, ExtraArgs=extra_args or {})
        logger.info("Uploaded %s to s3://%s/%s", file_path, bucket, key)
    except (BotoCoreError, ClientError):
        logger.exception("Failed to upload %s to s3://%s/%s", file_path, bucket, key)
        raise


def upload_files(
    *,
    bucket: str,
    prefix: str,
    files: Iterable[Path],
    region_name: Optional[str] = None,
) -> None:
    prefix = prefix.strip("/")
    for file_path in files:
        key = f"{prefix}/{file_path.name}" if prefix else file_path.name
        content_type = _guess_content_type(file_path)
        upload_file(
            bucket=bucket,
            key=key,
            file_path=file_path,
            content_type=content_type,
            region_name=region_name,
        )


def _guess_content_type(path: Path) -> Optional[str]:
    if path.suffix == ".json":
        return "application/json"
    if path.suffix in {".xls", ".xlsx"}:
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return None

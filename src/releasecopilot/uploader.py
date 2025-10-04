"""Utilities for uploading audit artifacts to Amazon S3."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)


def build_s3_client(*, region_name: Optional[str] = None):
    """Return a boto3 S3 client configured for ``region_name``."""

    return boto3.client("s3", region_name=region_name)


def put_object(
    bucket: str,
    key: str,
    body: bytes | str,
    *,
    client=None,
    region_name: Optional[str] = None,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
) -> None:
    """Write a single object to S3 using server-side encryption."""

    client = client or build_s3_client(region_name=region_name)
    payload = body.encode("utf-8") if isinstance(body, str) else body
    extra_args: Dict[str, str] = {"ServerSideEncryption": "AES256"}
    if content_type:
        extra_args["ContentType"] = content_type
    if metadata:
        extra_args["Metadata"] = {key: str(value) for key, value in metadata.items() if value is not None}
    client.put_object(Bucket=bucket, Key=key, Body=payload, **extra_args)


def upload_directory(
    bucket: str,
    prefix: str,
    local_dir: Path | str,
    subdir: str,
    *,
    client=None,
    region_name: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
) -> None:
    """Upload the contents of ``local_dir`` into ``s3://bucket/prefix/subdir``.

    Parameters
    ----------
    bucket:
        Destination S3 bucket.
    prefix:
        Base prefix for the upload (without the trailing ``subdir``).
    local_dir:
        Directory whose files will be uploaded.
    subdir:
        Name of the subdirectory to append under ``prefix`` (e.g. ``"reports"``).
    client:
        Optional boto3 S3 client. When omitted, a client is created using
        :func:`build_s3_client` and ``region_name``.
    region_name:
        AWS region for the boto3 client when ``client`` is not supplied.
    metadata:
        Optional metadata dictionary to attach to every object.
    """

    base_path = Path(local_dir)
    if not base_path.exists():
        logger.info("Local directory %s does not exist; skipping upload.", base_path)
        return

    files = [path for path in sorted(base_path.rglob("*")) if path.is_file()]
    if not files:
        logger.info("No files found in %s; nothing to upload.", base_path)
        return

    client = client or build_s3_client(region_name=region_name)

    normalized_prefix = prefix.strip("/")
    normalized_subdir = subdir.strip("/")
    combined_prefix = "/".join(filter(None, [normalized_prefix, normalized_subdir]))

    normalized_metadata = {
        key: str(value)
        for key, value in (metadata or {}).items()
        if value is not None
    }

    for file_path in files:
        relative_key = file_path.relative_to(base_path)
        key = "/".join(
            filter(None, [combined_prefix, str(relative_key).replace("\\", "/")])
        )
        extra_args = {"ServerSideEncryption": "AES256"}
        if normalized_metadata:
            extra_args["Metadata"] = normalized_metadata
        content_type = _guess_content_type(file_path)
        if content_type:
            extra_args["ContentType"] = content_type

        try:
            client.upload_file(str(file_path), bucket, key, ExtraArgs=extra_args)
        except (BotoCoreError, ClientError):  # pragma: no cover - network failure path
            logger.exception("Failed to upload %s to s3://%s/%s", file_path, bucket, key)
            raise
        logger.info("Uploaded %s to s3://%s/%s", file_path, bucket, key)


def _guess_content_type(path: Path) -> Optional[str]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "application/json"
    if suffix in {".xls", ".xlsx"}:
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return None


__all__ = ["build_s3_client", "put_object", "upload_directory"]


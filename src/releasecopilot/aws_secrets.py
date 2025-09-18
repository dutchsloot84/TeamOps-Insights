"""Minimal AWS Secrets Manager helper."""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except Exception:  # pragma: no cover - boto3 is an optional dependency at test time
    boto3 = None  # type: ignore[assignment]
    BotoCoreError = ClientError = Exception  # type: ignore[assignment]


@lru_cache(maxsize=None)
def _client():  # pragma: no cover - exercised via get_secret
    if boto3 is None:  # pragma: no cover - defensive; boto3 is expected
        raise RuntimeError("boto3 is required to access AWS Secrets Manager")
    return boto3.client("secretsmanager")


@lru_cache(maxsize=None)
def get_secret(name: str) -> Optional[str]:
    """Fetch ``name`` from AWS Secrets Manager, caching the result."""

    if not name:
        return None

    try:
        client = _client()
    except Exception:  # pragma: no cover - client creation errors are propagated
        return None

    try:
        response = client.get_secret_value(SecretId=name)
    except (ClientError, BotoCoreError):
        return None

    secret = response.get("SecretString")
    if secret is not None:
        return secret

    binary_secret = response.get("SecretBinary")
    if isinstance(binary_secret, (bytes, bytearray)):
        try:
            return binary_secret.decode("utf-8")
        except Exception:  # pragma: no cover - unexpected encoding issues
            return None

    return None

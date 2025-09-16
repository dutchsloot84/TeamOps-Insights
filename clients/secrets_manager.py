"""Helpers for loading secrets from environment variables or AWS Secrets Manager."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load local .env variables as a fallback when running outside AWS.
load_dotenv()


@dataclass
class SecretResult:
    """Container for a secret payload."""

    name: str
    value: Dict[str, Any]


class SecretsManager:
    """Retrieves secrets from AWS Secrets Manager with graceful degradation."""

    def __init__(self, region_name: Optional[str] = None) -> None:
        self.region_name = region_name
        self._client = None

    def _get_client(self):
        if self._client is None and self.region_name:
            try:
                self._client = boto3.client("secretsmanager", region_name=self.region_name)
            except (BotoCoreError, ClientError):
                logger.exception("Unable to create Secrets Manager client")
                self._client = None
        return self._client

    def get_secret(self, secret_id: Optional[str]) -> SecretResult | None:
        """Retrieve a JSON secret, returning an empty dict on failure."""
        if not secret_id:
            return None

        client = self._get_client()
        if client is None:
            logger.info("Secrets Manager client unavailable; skipping fetch for %s", secret_id)
            return None

        try:
            response = client.get_secret_value(SecretId=secret_id)
            secret_string = response.get("SecretString")
            if secret_string:
                payload = json.loads(secret_string)
            else:
                payload = json.loads(response["SecretBinary"].decode("utf-8"))
            logger.debug("Loaded secret %s", secret_id)
            return SecretResult(name=secret_id, value=payload)
        except (BotoCoreError, ClientError, json.JSONDecodeError):
            logger.exception("Failed to retrieve secret %s", secret_id)
            return None


class CredentialStore:
    """Resolves credential values with the following priority order.

    1. Explicit overrides provided via kwargs.
    2. Environment variables.
    3. AWS Secrets Manager payload (if configured).
    """

    def __init__(self, secrets_manager: SecretsManager | None = None) -> None:
        self.secrets_manager = secrets_manager or SecretsManager()

    def get(  # type: ignore[override]
        self,
        key: str,
        *,
        env_var: Optional[str] = None,
        secret_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        default: Optional[Any] = None,
    ) -> Any:
        env_name = env_var or key
        if env_name and env_name in os.environ:
            return os.environ[env_name]

        secret_payload: Dict[str, Any] = {}
        secret = self.secrets_manager.get_secret(secret_id) if secret_id else None
        if secret:
            secret_payload = secret.value
            if secret_key and secret_key in secret_payload:
                return secret_payload[secret_key]
            if key in secret_payload:
                return secret_payload[key]

        return default

    def get_all_from_secret(self, secret_id: Optional[str]) -> Dict[str, Any]:
        secret = self.secrets_manager.get_secret(secret_id) if secret_id else None
        return secret.value if secret else {}

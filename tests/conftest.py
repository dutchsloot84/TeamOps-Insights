"""Shared pytest fixtures for Release Copilot tests."""

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any, Dict

import pytest


@pytest.fixture(autouse=True)
def _disable_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent network access during the test suite.

    Several modules rely on optional network calls (e.g. fetching secrets).
    Tests should never reach out to external services, so we patch the most
    common socket entry points to raise a helpful error if triggered.
    """

    def _guard(*args: object, **kwargs: object) -> socket.socket:  # type: ignore[override]
        raise RuntimeError("Network access is disabled during tests.")

    monkeypatch.setattr(socket, "socket", _guard)
    monkeypatch.setattr(socket, "create_connection", _guard)


@pytest.fixture(autouse=True)
def _mock_secrets_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent real AWS Secrets Manager access during tests.

    The config loader uses ``CredentialStore.get_all_from_secret``; stub it to
    return an empty mapping so tests never reach AWS.
    """

    def _no_secrets(self, arn):
        return {}

    monkeypatch.setattr(
        "clients.secrets_manager.CredentialStore.get_all_from_secret",
        _no_secrets,
        raising=True,
    )


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the shared fixtures directory."""

    return Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def load_json() -> "LoadJSONFn":
    """Helper fixture to load JSON fixtures by filename."""

    def _loader(path: str | Path) -> Dict[str, Any]:
        file_path = Path(path)
        with file_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    return _loader


class LoadJSONFn:
    """Protocol-like helper for typing the ``load_json`` fixture."""

    def __call__(
        self, path: str | Path
    ) -> Dict[str, Any]:  # pragma: no cover - documentation only
        ...

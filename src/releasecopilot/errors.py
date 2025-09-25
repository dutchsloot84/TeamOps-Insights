"""Application specific exception hierarchy."""
from __future__ import annotations

from typing import Any


class ReleaseCopilotError(RuntimeError):
    """Base exception that carries structured context."""

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.context = context or {}


class JiraTokenRefreshError(ReleaseCopilotError):
    """Raised when Jira token refresh fails."""


class JiraQueryError(ReleaseCopilotError):
    """Raised when Jira issue search fails."""


class BitbucketRequestError(ReleaseCopilotError):
    """Raised when Bitbucket requests fail."""


__all__ = [
    "ReleaseCopilotError",
    "JiraTokenRefreshError",
    "JiraQueryError",
    "BitbucketRequestError",
]

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def load_dotenv(*, dotenv_path: str | os.PathLike[str] | None = None, **_: Any) -> bool:
    """Lightweight fallback loader that mimics python-dotenv for tests."""

    path = Path(dotenv_path) if dotenv_path else Path.cwd() / ".env"
    if not path.exists():
        return False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key] = value
    return True


__all__ = ["load_dotenv"]

#!/usr/bin/env python3
"""Wrapper to execute the CDK app with the active interpreter."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    app_path = Path(__file__).resolve().parent / "app.py"
    argv = [sys.executable, str(app_path), *sys.argv[1:]]
    os.execv(sys.executable, argv)


if __name__ == "__main__":
    main()

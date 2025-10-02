#!/usr/bin/env python3
"""Print information about the Python runtime used for CDK commands."""
from __future__ import annotations

import platform
import sys


def main() -> None:
    print(f"sys.executable: {sys.executable}")
    print(f"python_version: {platform.python_version()}")
    print(f"platform: {platform.system()}")


if __name__ == "__main__":
    main()

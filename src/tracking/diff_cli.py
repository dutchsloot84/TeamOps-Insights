"""Command line interface for diffing ReleaseCopilot audit runs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .diff import diff_runs, render_diff_markdown


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old", required=True, type=Path, help="Path to the previous JSON artifact")
    parser.add_argument("--new", required=True, type=Path, help="Path to the new JSON artifact")
    parser.add_argument("--out", type=Path, help="Optional path to write the markdown summary")
    parser.add_argument("--json", dest="json_out", type=Path, help="Optional path to write the raw diff JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    old_payload = _load_json(args.old)
    new_payload = _load_json(args.new)

    diff = diff_runs(old_payload, new_payload)
    markdown = render_diff_markdown(diff)

    if args.out:
        args.out.write_text(markdown + "\n", encoding="utf-8")
    if args.json_out:
        args.json_out.write_text(json.dumps(diff, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(markdown)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

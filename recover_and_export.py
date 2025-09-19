"""Standalone recovery CLI that rebuilds export artifacts from cached JSON."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Iterable

from src.export.exporter import build_export_payload, export_all


LOGGER = logging.getLogger("recover")

REQUIRED_FILES = {
    "stories": "stories.json",
    "commits": "commits.json",
    "links": "links.json",
    "summary": "summary.json",
}


class MissingInputError(RuntimeError):
    """Raised when a required cached payload is missing."""


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild export artifacts from cached payloads")
    parser.add_argument("--input-dir", default="temp_data/", help="Directory containing cached JSON payloads")
    parser.add_argument("--out-dir", default="reports/", help="Directory to write regenerated reports")
    parser.add_argument(
        "--format",
        default="excel,json",
        help="Comma separated list of formats to rebuild (excel,json)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args(argv)


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise MissingInputError(f"Required input not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_inputs(input_dir: Path) -> Dict[str, Dict[str, Any]]:
    inputs: Dict[str, Dict[str, Any]] = {}
    for key, filename in REQUIRED_FILES.items():
        path = input_dir / filename
        payload = _load_json(path)
        inputs[key] = payload
        if isinstance(payload, dict):
            metadata = {"keys": sorted(payload.keys())}
        else:
            metadata = {"length": len(payload) if hasattr(payload, "__len__") else None}
        LOGGER.info(json.dumps({"event": "input_loaded", "name": key, "path": str(path), **metadata}))
    return inputs


def _ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _ensure_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    raise TypeError("Summary payload must be a JSON object")


def _extract(payload: Dict[str, Any], *candidates: str) -> Any:
    for candidate in candidates:
        if candidate in payload:
            return payload[candidate]
    return payload


def build_payload_from_inputs(inputs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    return build_export_payload(
        data={
            "summary": _ensure_dict(inputs["summary"]),
            "stories_with_no_commits": _ensure_list(
                _extract(inputs["stories"], "stories_with_no_commits", "stories", "items")
            ),
            "orphan_commits": _ensure_list(_extract(inputs["commits"], "orphan_commits", "commits", "items")),
            "commit_story_mapping": _ensure_list(
                _extract(inputs["links"], "commit_story_mapping", "links", "items")
            ),
        }
    )


def parse_formats(value: str) -> Iterable[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.verbose)

    input_dir = Path(args.input_dir)
    output_dir = Path(args.out_dir)

    try:
        inputs = load_inputs(input_dir)
        payload = build_payload_from_inputs(inputs)
        outputs = export_all(payload, out_dir=output_dir, formats=parse_formats(args.format))
    except MissingInputError as exc:
        LOGGER.error(json.dumps({"event": "missing_input", "message": str(exc)}))
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - defensive guard
        LOGGER.exception("Unexpected failure during recovery")
        print(f"Recovery failed: {exc}", file=sys.stderr)
        return 1

    LOGGER.info(json.dumps({"event": "outputs_written", "outputs": {k: str(v) for k, v in outputs.items()}}))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())

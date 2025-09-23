"""Golden-file verification tests for the JSON exporter."""
from __future__ import annotations

import json
from pathlib import Path

from exporters.json_exporter import JSONExporter


def test_json_exporter_produces_expected_payload(
    tmp_path, fixtures_dir, load_json
) -> None:
    """Exported JSON should match the golden artifact byte-for-byte."""

    payload = {
        "stories": load_json(fixtures_dir / "stories.json"),
        "commits": load_json(fixtures_dir / "commits.json"),
        "links": load_json(fixtures_dir / "links.json"),
    }

    exporter = JSONExporter(tmp_path)
    output_path = exporter.export(payload, filename="golden.json")

    golden_path = Path(__file__).resolve().parent / "golden" / "exporter_expected.json"

    output_text = output_path.read_text(encoding="utf-8").strip()
    golden_text = golden_path.read_text(encoding="utf-8").strip()

    assert output_text == golden_text
    assert json.loads(output_text) == json.loads(golden_text)

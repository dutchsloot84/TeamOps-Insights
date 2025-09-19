from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pandas.testing as pdt
import pytest


FIXTURE_DIR = Path("tests/fixtures/temp_data")
GOLDEN_DIR = Path("tests/fixtures/golden")
EXPECTED_WORKBOOK = GOLDEN_DIR / "audit_results_workbook.json"


def _load_workbook(path: Path) -> dict[str, pd.DataFrame]:
    with pd.ExcelFile(path) as excel_file:
        return {
            sheet: pd.read_excel(excel_file, sheet_name=sheet).fillna("<NA>")
            for sheet in excel_file.sheet_names
        }


def _assert_workbook_matches_expected(actual: Path) -> None:
    workbook_expectations = json.loads(EXPECTED_WORKBOOK.read_text())
    actual_sheets = _load_workbook(actual)

    assert set(actual_sheets) == set(workbook_expectations)

    for sheet, actual_df in actual_sheets.items():
        expected_records = workbook_expectations[sheet]
        expected_df = pd.DataFrame(expected_records)
        if expected_df.empty:
            expected_df = pd.DataFrame(columns=actual_df.columns)
        expected_df = expected_df.reindex(columns=actual_df.columns)
        expected_df = expected_df.fillna("<NA>")
        pdt.assert_frame_equal(
            actual_df.reset_index(drop=True),
            expected_df.reset_index(drop=True),
            check_dtype=False,
            check_like=True,
        )


@pytest.mark.integration
def test_recover_and_export_matches_golden(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    shutil.copytree(FIXTURE_DIR, input_dir)
    output_dir = tmp_path / "reports"

    result = subprocess.run(
        [sys.executable, "recover_and_export.py", "--input-dir", str(input_dir), "--out-dir", str(output_dir)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr

    generated_json = output_dir / "audit_results.json"
    generated_excel = output_dir / "audit_results.xlsx"
    generated_summary = output_dir / "summary.json"

    assert generated_json.read_text() == (GOLDEN_DIR / "audit_results.json").read_text()
    _assert_workbook_matches_expected(generated_excel)
    assert json.loads(generated_summary.read_text()) == json.loads((GOLDEN_DIR / "summary.json").read_text())


def test_missing_inputs_exit_with_error(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "stories.json").write_text("[]", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "recover_and_export.py", "--input-dir", str(input_dir), "--out-dir", str(tmp_path / "reports")],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Required input not found" in result.stderr


def test_format_flag_limits_outputs(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    shutil.copytree(FIXTURE_DIR, input_dir)
    output_dir = tmp_path / "reports"

    result = subprocess.run(
        [
            sys.executable,
            "recover_and_export.py",
            "--input-dir",
            str(input_dir),
            "--out-dir",
            str(output_dir),
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (output_dir / "audit_results.json").exists()
    assert not (output_dir / "audit_results.xlsx").exists()
    assert (output_dir / "summary.json").exists()

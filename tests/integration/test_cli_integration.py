import subprocess


def test_cli_dry_run(tmp_path):
    out_dir = tmp_path / "artifacts"
    out_dir.mkdir()

    result = subprocess.run(
        [
            "python",
            "-m",
            "src.cli.main",
            "--fix-version",
            "TEST-1",
            "--dry-run",
            "--output",
            str(out_dir),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "TEST-1" in result.stdout

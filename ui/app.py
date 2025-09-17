"""Streamlit UI skeleton for triggering release audits."""
from __future__ import annotations

import json
import subprocess
from datetime import date
from pathlib import Path
from typing import List

import streamlit as st

st.set_page_config(page_title="releasecopilot-ai", layout="wide")

st.title("ReleaseCopilot-AI")

with st.sidebar:
    st.header("Audit Parameters")
    fix_version = st.text_input("Fix Version", "MOB-1.0.0")
    repos_raw = st.text_input("Repositories (comma separated)", "")
    branches_raw = st.text_input("Branches (comma separated)", "")
    freeze_date = st.date_input("Freeze Date", value=date.today())
    develop_only = st.toggle("Develop branch only", value=False)
    use_cache = st.toggle("Use cached payloads", value=True)
    upload_s3 = st.toggle("Upload to S3", value=False)
    run_btn = st.button("Run Audit")

output_dir = Path("artifacts")
output_dir.mkdir(exist_ok=True)

if run_btn:
    cmd: List[str] = [
        "python",
        "-m",
        "src.cli.main",
        "--fix-version",
        fix_version,
        "--output",
        str(output_dir),
    ]
    if repos_raw.strip():
        cmd.append("--repos")
        cmd.extend([repo.strip() for repo in repos_raw.split(",") if repo.strip()])
    if branches_raw.strip():
        cmd.append("--branches")
        cmd.extend([branch.strip() for branch in branches_raw.split(",") if branch.strip()])
    if develop_only:
        cmd.append("--develop-only")
    if use_cache:
        cmd.append("--use-cache")
    if upload_s3:
        cmd.append("--upload-s3")
    if freeze_date:
        cmd.extend(["--freeze-date", freeze_date.isoformat()])

    st.write("Running command:")
    st.code(" ".join(cmd))

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        st.subheader("CLI Output")
        st.code(result.stdout)
    if result.stderr:
        st.subheader("CLI Errors")
        st.code(result.stderr)
    if result.returncode != 0:
        st.error("Audit failed; check the logs above for details.")

summary_path = output_dir / "summary.json"
if summary_path.exists():
    st.subheader("Audit Summary")
    st.json(json.loads(summary_path.read_text(encoding="utf-8")))

for filename in ("audit_results.xlsx", "audit_results.json"):
    file_path = output_dir / filename
    if file_path.exists():
        with file_path.open("rb") as fh:
            st.download_button(
                label=f"Download {filename}",
                data=fh,
                file_name=filename,
            )

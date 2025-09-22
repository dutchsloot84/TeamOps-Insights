"""Streamlit dashboard for browsing audit outputs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

import boto3
import pandas as pd
import requests
import streamlit as st

from ui.data_source import RunRef, load_local_reports, load_s3_json, load_s3_listing
from ui import transform
from tracking import api as tracking_api
from tracking.diff import render_diff_markdown

st.set_page_config(page_title="ReleaseCopilot Audit Dashboard", layout="wide")


@st.cache_data(show_spinner=False)
def _cached_local(path_str: str) -> Dict[str, object]:
    return load_local_reports(path_str)


@st.cache_data(show_spinner=False)
def _cached_s3_listing(bucket: str, prefix: str) -> list[RunRef]:
    return load_s3_listing(bucket, prefix)


@st.cache_data(show_spinner=False)
def _cached_s3_json(bucket: str, key: str) -> Dict[str, object]:
    return load_s3_json(bucket, key)


@st.cache_data(show_spinner=False)
def _cached_excel_link(bucket: str, key: str) -> Optional[str]:
    client = boto3.client("s3")
    try:
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=900,
        )
    except Exception:  # pragma: no cover - network interaction
        return None


st.title("ReleaseCopilot Audit Browser")

st.markdown(
    "<style>.metric-container>div{background:var(--background-color-secondary);padding:0.75rem;border-radius:0.5rem}</style>",
    unsafe_allow_html=True,
)

selected_report: Optional[Dict[str, object]] = None
current_json_path: Optional[Path] = None
current_excel_path: Optional[Path] = None
current_run_ref: Optional[RunRef] = None
current_bucket: Optional[str] = None

previous_report: Optional[Dict[str, object]] = None
previous_label: Optional[str] = None
previous_excel_link: Optional[str] = None

with st.sidebar:
    st.header("Data source")
    source = st.radio("Select source", ("Local", "Amazon S3"), index=0)

    if source == "Local":
        reports_dir = st.text_input("Reports folder", "reports")
        if reports_dir:
            try:
                payload = _cached_local(reports_dir)
                selected_report = payload.get("data")  # type: ignore[assignment]
                current_json_path = payload.get("json_path")  # type: ignore[assignment]
                current_excel_path = payload.get("excel_path")  # type: ignore[assignment]
            except Exception as exc:  # pragma: no cover - UI feedback
                st.error(str(exc))
    else:
        bucket = st.text_input("S3 bucket", key="bucket")
        prefix = st.text_input("Prefix", key="prefix", help="Optional folder within the bucket")
        run_options: list[RunRef] = []
        if bucket:
            try:
                run_options = _cached_s3_listing(bucket, prefix)
            except Exception as exc:  # pragma: no cover - UI feedback
                st.error(str(exc))
        if run_options:
            option_labels = {run.label(): run for run in run_options}
            selection = st.selectbox("Available runs", list(option_labels.keys()))
            if selection:
                current_run_ref = option_labels[selection]
                current_bucket = bucket
                try:
                    selected_report = _cached_s3_json(bucket, current_run_ref.json_key)
                except Exception as exc:  # pragma: no cover - UI feedback
                    st.error(str(exc))
        else:
            if bucket:
                st.info("No JSON reports found for the provided prefix.")

    compare_enabled = False
    diff_api_url = ""
    if selected_report:
        st.markdown("---")
        compare_enabled = st.toggle("Compare to previous run")
        if compare_enabled:
            diff_api_url = st.text_input("Diff API endpoint", help="POST endpoint for the #24 diff API")
            if source == "Local":
                uploaded = st.file_uploader("Upload previous JSON", type="json")
                if uploaded:
                    previous_bytes = uploaded.getvalue()
                    if previous_bytes:
                        previous_report = json.loads(previous_bytes.decode("utf-8"))
                    previous_label = uploaded.name
            else:
                if current_run_ref and current_bucket:
                    candidates = [run for run in run_options if run.json_key != current_run_ref.json_key]
                    if candidates:
                        labels = {run.label(): run for run in candidates}
                        previous_choice = st.selectbox("Previous run", list(labels.keys()))
                        if previous_choice:
                            prev_ref = labels[previous_choice]
                            previous_label = previous_choice
                            try:
                                previous_report = _cached_s3_json(current_bucket, prev_ref.json_key)
                                if prev_ref.excel_key:
                                    previous_excel_link = _cached_excel_link(current_bucket, prev_ref.excel_key)
                            except Exception as exc:  # pragma: no cover - UI feedback
                                st.error(str(exc))
                    else:
                        st.info("No other runs available for comparison.")

if not selected_report:
    st.info("Select a reports directory or S3 run from the sidebar to begin.")
    st.stop()

stories_with_df, stories_without_df = transform.prepare_story_tables(selected_report)
orphan_df = transform.build_orphan_dataframe(selected_report)
filter_options = transform.get_filter_options(stories_with_df, stories_without_df, orphan_df)

filters: Dict[str, object] = {}

with st.sidebar:
    st.header("Filters")
    selected_fix_versions = st.multiselect("Fix versions", filter_options["fix_versions"])
    if selected_fix_versions:
        filters["fix_versions"] = selected_fix_versions

    selected_statuses = st.multiselect("Jira status", filter_options["statuses"])
    if selected_statuses:
        filters["statuses"] = selected_statuses

    selected_assignees = st.multiselect("Assignee", filter_options["assignees"])
    if selected_assignees:
        filters["assignees"] = selected_assignees

    selected_labels = st.multiselect("Component / Label", filter_options["components_labels"])
    if selected_labels:
        filters["components_labels"] = selected_labels

    selected_repos = st.multiselect("Repository", filter_options["repositories"])
    if selected_repos:
        filters["repositories"] = selected_repos

    selected_branches = st.multiselect("Branch", filter_options["branches"])
    if selected_branches:
        filters["branches"] = selected_branches

    if filter_options["date_range"]:
        min_date, max_date = filter_options["date_range"]
        default_start = min_date.date()
        default_end = max_date.date()
        chosen_dates = st.date_input(
            "Commit date range",
            (default_start, default_end),
            min_value=default_start,
            max_value=default_end,
        )
        if isinstance(chosen_dates, tuple) and len(chosen_dates) == 2:
            start_dt = pd.Timestamp(chosen_dates[0])
            end_dt = pd.Timestamp(chosen_dates[1]) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
            filters["date_range"] = (start_dt, end_dt)

filtered_with_df, filtered_without_df = transform.filter_story_tables(
    stories_with_df, stories_without_df, filters
)
filtered_orphan_df = transform.filter_orphan_commits(orphan_df, filters)

filtered_total = len(filtered_with_df) + len(filtered_without_df)
coverage = round((len(filtered_with_df) / filtered_total * 100) if filtered_total else 0.0, 2)

metric_cols = st.columns(5, gap="small")
metric_cols[0].metric("Total stories", filtered_total)
metric_cols[1].metric("With commits", len(filtered_with_df))
metric_cols[2].metric("Without commits", len(filtered_without_df))
metric_cols[3].metric("Orphan commits", len(filtered_orphan_df))
metric_cols[4].metric("Coverage %", f"{coverage:.2f}")

source_details = []
if current_json_path:
    source_details.append(f"Loaded from `{current_json_path}`")
if current_run_ref and current_bucket:
    source_details.append(
        f"Loaded `{current_run_ref.json_key}` from `s3://{current_bucket}/{current_run_ref.json_key}`"
    )
if source_details:
    st.caption("\n".join(source_details))

stories_tab, missing_tab, orphan_tab, compare_tab = st.tabs(
    ["Stories with commits", "Stories without commits", "Orphan commits", "Compare"]
)

with stories_tab:
    st.dataframe(filtered_with_df, use_container_width=True)
    st.download_button(
        "Download CSV",
        filtered_with_df.to_csv(index=False).encode("utf-8"),
        file_name="stories_with_commits.csv",
        mime="text/csv",
    )

with missing_tab:
    st.dataframe(filtered_without_df, use_container_width=True)
    st.download_button(
        "Download CSV",
        filtered_without_df.to_csv(index=False).encode("utf-8"),
        file_name="stories_without_commits.csv",
        mime="text/csv",
    )

with orphan_tab:
    st.dataframe(filtered_orphan_df, use_container_width=True)
    st.download_button(
        "Download CSV",
        filtered_orphan_df.to_csv(index=False).encode("utf-8"),
        file_name="orphan_commits.csv",
        mime="text/csv",
    )

    if current_excel_path:
        with current_excel_path.open("rb") as excel_fh:
            st.download_button(
                "Download Excel report",
                data=excel_fh.read(),
                file_name=current_excel_path.name,
            )
    elif current_run_ref and current_run_ref.excel_key and current_bucket:
        excel_link = _cached_excel_link(current_bucket, current_run_ref.excel_key)
        if excel_link:
            st.markdown(f"[Download Excel report]({excel_link})")
        else:
            st.caption(
                f"Excel: s3://{current_bucket}/{current_run_ref.excel_key} (unable to generate presigned URL)"
            )

with compare_tab:
    if not compare_enabled:
        st.info("Enable comparison from the sidebar to diff against another run.")
    elif not previous_report:
        st.warning("Select or upload a previous run to compare.")
    else:
        current_metrics = transform.compute_kpis(selected_report)
        previous_metrics = transform.compute_kpis(previous_report)
        diff_payload = tracking_api.compare(previous_report, selected_report)

        diff_cols = st.columns(5, gap="small")
        diff_cols[0].metric(
            "Total stories",
            current_metrics["total_stories"],
            current_metrics["total_stories"] - previous_metrics["total_stories"],
        )
        diff_cols[1].metric(
            "With commits",
            current_metrics["stories_with_commits"],
            current_metrics["stories_with_commits"] - previous_metrics["stories_with_commits"],
        )
        diff_cols[2].metric(
            "Without commits",
            current_metrics["stories_without_commits"],
            current_metrics["stories_without_commits"] - previous_metrics["stories_without_commits"],
        )
        diff_cols[3].metric(
            "Orphan commits",
            current_metrics["orphan_commits"],
            current_metrics["orphan_commits"] - previous_metrics["orphan_commits"],
        )
        diff_cols[4].metric(
            "Coverage %",
            f"{diff_payload['coverage_current']:.2f}",
            diff_payload["coverage_delta"],
        )

        st.markdown("### Summary")
        st.markdown(render_diff_markdown(diff_payload))

        def _maybe_render_table(title: str, rows: list[dict[str, object]] | list[str]) -> None:
            if not rows:
                return
            st.markdown(f"#### {title}")
            if rows and isinstance(rows[0], dict):
                df = pd.DataFrame(rows)
            else:
                df = pd.DataFrame({"value": rows})
            if "commit_ids" in df.columns:
                df["commit_ids"] = df["commit_ids"].apply(
                    lambda value: ", ".join(value) if isinstance(value, list) else value
                )
            st.dataframe(df, use_container_width=True)

        _maybe_render_table("Stories added", [{"key": key} for key in diff_payload["stories_added"]])
        _maybe_render_table("Stories removed", [{"key": key} for key in diff_payload["stories_removed"]])
        _maybe_render_table("Status changes", diff_payload["status_changes"])
        _maybe_render_table("Assignee changes", diff_payload["assignee_changes"])
        _maybe_render_table("Commits added", diff_payload["commits_added"])
        _maybe_render_table("Commits removed", diff_payload["commits_removed"])
        _maybe_render_table("New orphan commits", diff_payload["new_orphans"])
        _maybe_render_table("Resolved orphan commits", diff_payload["resolved_orphans"])

        st.markdown("### Diff API")
        if diff_api_url:
            if st.button("Call diff API"):
                try:
                    response = requests.post(
                        diff_api_url,
                        json={
                            "current": selected_report,
                            "previous": previous_report,
                        },
                        timeout=30,
                    )
                    response.raise_for_status()
                    try:
                        st.json(response.json())
                    except ValueError:
                        st.text(response.text)
                except requests.RequestException as exc:  # pragma: no cover - network interaction
                    st.error(f"Diff API request failed: {exc}")
        else:
            st.caption("Provide a diff API endpoint in the sidebar to trigger comparisons.")

        if previous_label:
            st.caption(f"Comparing against: {previous_label}")
        if previous_excel_link:
            st.markdown(f"[Download previous Excel report]({previous_excel_link})")

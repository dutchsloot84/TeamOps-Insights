#!/usr/bin/env python3
r"""Generate Release Copilot history check-ins.

This script collects project activity (issues, pull requests, decisions, and artifacts)
and renders a Markdown snapshot using ``docs/history/HISTORY_TEMPLATE.md``. It also
maintains ``docs/context/context-index.json`` for machine-readable discovery.

Usage examples::

    python scripts/generate_history.py --since 7d --output docs/history
    python scripts/generate_history.py --since 2025-01-01T00:00:00Z --repo owner/name

Environment variables::

    GITHUB_TOKEN                 GitHub token (defaults to workflow token in CI)
    HISTORIAN_ENABLE_JIRA        When ``true`` parse commit messages for Jira keys.
    HISTORIAN_ENABLE_S3_ARTIFACTS When ``true`` render artifact entries (requires --artifacts-file or env path).
    HISTORIAN_ENABLE_HASH        When ``true`` include sha256 hashes from artifact data.
    HISTORIAN_ARTIFACTS_FILE     Default path for ``--artifacts-file``.

The optional Jira integration currently scans local commit messages for keys matching
``[A-Z]+-\d+`` and surfaces them in the Notes & Decisions section. Teams can extend this
hook to call Jira APIs or execute JQL queries using additional environment variables.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import requests

LOGGER = logging.getLogger(__name__)
ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _parse_since(value: str) -> dt.datetime:
    """Parse --since values such as ``7d`` or ISO timestamps."""

    if not value:
        raise ValueError("--since cannot be empty")

    value = value.strip()
    now = dt.datetime.now(dt.timezone.utc)

    if value.endswith("d") and value[:-1].isdigit():
        days = int(value[:-1])
        return now - dt.timedelta(days=days)
    if value.endswith("h") and value[:-1].isdigit():
        hours = int(value[:-1])
        return now - dt.timedelta(hours=hours)

    # Try ISO 8601
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            "Unable to parse --since value. Use relative formats like '7d' or '24h' "
            "or provide an ISO timestamp (e.g. 2024-12-31T00:00:00Z)."
        ) from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


@dataclass
class Issue:
    number: int
    title: str
    url: str
    closed_at: Optional[dt.datetime]
    assignees: List[str]
    labels: List[str]


@dataclass
class PullRequest:
    number: int
    title: str
    url: str
    merged_at: Optional[dt.datetime]
    author: Optional[str]


@dataclass
class HistoryDocument:
    markdown: str
    since: dt.datetime
    until: dt.datetime
    completed_count: int
    in_progress_count: int
    upcoming_count: int


class GithubClient:
    """Minimal GitHub REST API helper."""

    def __init__(self, repo: str, token: Optional[str] = None) -> None:
        self.repo = repo
        self.base_url = f"https://api.github.com/repos/{repo}"
        self.session = requests.Session()
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "release-copilot-git-historian",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.session.headers.update(headers)

    def paginate(self, url: str, params: Optional[dict] = None) -> Iterable[dict]:
        params = params.copy() if params else None
        while url:
            LOGGER.debug("GET %s params=%s", url, params)
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code >= 400:
                raise RuntimeError(
                    f"GitHub API error {response.status_code}: {response.text}"
                )
            yield from response.json()
            if "next" in response.links:
                url = response.links["next"]["url"]
                params = None
            else:
                break

    def list_closed_issues(self, since: dt.datetime) -> List[Issue]:
        params = {
            "state": "closed",
            "since": since.strftime(ISO_FORMAT),
            "per_page": 100,
            "sort": "updated",
            "direction": "desc",
        }
        results: List[Issue] = []
        for data in self.paginate(f"{self.base_url}/issues", params):
            if "pull_request" in data:
                continue
            closed_at = _parse_github_datetime(data.get("closed_at"))
            if closed_at and closed_at < since:
                continue
            issue = Issue(
                number=data["number"],
                title=data["title"],
                url=data["html_url"],
                closed_at=closed_at,
                assignees=[a["login"] for a in data.get("assignees", [])],
                labels=[lbl["name"] for lbl in data.get("labels", [])],
            )
            results.append(issue)
        return results

    def list_open_issues_with_label(self, label: str) -> List[Issue]:
        params = {
            "state": "open",
            "per_page": 100,
            "labels": label,
            "sort": "updated",
            "direction": "desc",
        }
        results: List[Issue] = []
        for data in self.paginate(f"{self.base_url}/issues", params):
            if "pull_request" in data:
                continue
            issue = Issue(
                number=data["number"],
                title=data["title"],
                url=data["html_url"],
                closed_at=None,
                assignees=[a["login"] for a in data.get("assignees", [])],
                labels=[lbl["name"] for lbl in data.get("labels", [])],
            )
            results.append(issue)
        return results

    def list_merged_prs(self, since: dt.datetime) -> List[PullRequest]:
        params = {
            "state": "closed",
            "per_page": 100,
            "sort": "updated",
            "direction": "desc",
        }
        results: List[PullRequest] = []
        for data in self.paginate(f"{self.base_url}/pulls", params):
            merged_at = _parse_github_datetime(data.get("merged_at"))
            updated_at = _parse_github_datetime(data.get("updated_at"))
            if updated_at and updated_at < since:
                break
            if not merged_at or merged_at < since:
                continue
            pr = PullRequest(
                number=data["number"],
                title=data["title"],
                url=data["html_url"],
                merged_at=merged_at,
                author=(data.get("user") or {}).get("login"),
            )
            results.append(pr)
        return results


def _parse_github_datetime(value: Optional[str]) -> Optional[dt.datetime]:
    if not value:
        return None
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
        dt.timezone.utc
    )


def _determine_repo(arg_repo: Optional[str]) -> str:
    if arg_repo:
        return arg_repo
    env_repo = os.getenv("GITHUB_REPOSITORY")
    if env_repo:
        return env_repo
    try:
        output = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        output = ""
    if output:
        # Support HTTPS or SSH remotes.
        if output.endswith(".git"):
            output = output[:-4]
        if output.startswith("git@"):
            _, remainder = output.split(":", 1)
            return remainder
        if output.startswith("https://"):
            parts = output.split("github.com/")
            if len(parts) == 2:
                return parts[1]
    raise ValueError(
        "Unable to determine repository. Pass --repo or set GITHUB_REPOSITORY."
    )


def _format_issue(issue: Issue) -> str:
    assignees = f" (@{' @'.join(issue.assignees)})" if issue.assignees else ""
    return f"- Issue [#{issue.number}]({issue.url}): {issue.title}{assignees}"


def _format_pr(pr: PullRequest) -> str:
    author = f" by @{pr.author}" if pr.author else ""
    merged = (
        pr.merged_at.strftime("%Y-%m-%d") if pr.merged_at else ""
    )
    merged_suffix = f" (merged {merged})" if merged else ""
    return f"- PR [#{pr.number}]({pr.url}): {pr.title}{author}{merged_suffix}"


def _format_section(items: Iterable[str]) -> str:
    items = list(items)
    if not items:
        return "_No updates_\n"
    return "\n".join(items) + "\n"


def _collect_notes_and_decisions(root: Path, since: dt.datetime) -> List[str]:
    notes: List[str] = []
    adr_dirs = [
        root / "docs" / "adr",
        root / "docs" / "adrs",
        root / "docs" / "decisions",
        root / "docs" / "architecture" / "adr",
    ]
    for adr_dir in adr_dirs:
        if adr_dir.exists():
            for path in sorted(adr_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
                mtime = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
                if mtime < since:
                    continue
                rel = path.relative_to(root)
                notes.append(f"- Updated ADR: [{path.stem}]({rel.as_posix()}) (modified {mtime.date()})")
    return notes


def _collect_jira_references(root: Path, since: dt.datetime) -> List[str]:
    if os.getenv("HISTORIAN_ENABLE_JIRA", "false").lower() != "true":
        return []
    pattern = os.getenv("HISTORIAN_JIRA_REGEX", r"[A-Z]+-\d+")
    try:
        log_output = subprocess.check_output(
            [
                "git",
                "log",
                f"--since={since.isoformat()}",
                "--pretty=%H %s",
            ],
            cwd=root,
        ).decode()
    except subprocess.CalledProcessError:
        LOGGER.warning("Failed to collect git log for Jira enrichment")
        return []
    regex = re.compile(pattern)
    references = {}
    for line in log_output.splitlines():
        if not line:
            continue
        commit, _, message = line.partition(" ")
        for match in regex.findall(message):
            references.setdefault(match, []).append(commit)
    if not references:
        return []
    items = []
    for key, commits in sorted(references.items()):
        commit_list = ", ".join(commit[:7] for commit in commits[:5])
        suffix = "" if len(commits) <= 5 else ", …"
        items.append(f"- Jira {key} linked to commits: {commit_list}{suffix}")
    return items


def _load_artifacts(path: Optional[Path]) -> List[dict]:
    if not path:
        return []
    if not path.exists():
        LOGGER.warning("Artifact file %s does not exist", path)
        return []
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return list(data.get("artifacts", []))


def _render_artifacts(artifacts: List[dict], include_hash: bool) -> str:
    if not artifacts:
        return "_No artifacts recorded_\n"
    lines = []
    for artifact in artifacts:
        name = artifact.get("name", "Artifact")
        s3_key = artifact.get("s3_key") or artifact.get("path")
        hash_value = artifact.get("hash") or artifact.get("sha256")
        if s3_key:
            entry = f"- **{name}** → `{s3_key}`"
        else:
            entry = f"- **{name}**"
        if include_hash and hash_value:
            entry += f" (sha256 `{hash_value}`)"
        lines.append(entry)
    return "\n".join(lines) + "\n"


def _ensure_history_index(
    index_path: Path,
    checkin_path: Path,
    since: dt.datetime,
    until: dt.datetime,
    completed_count: int,
    in_progress_count: int,
    upcoming_count: int,
) -> None:
    entry = {
        "date": until.date().isoformat(),
        "file": checkin_path.as_posix(),
        "since": since.isoformat(),
        "until": until.isoformat(),
        "counts": {
            "completed": completed_count,
            "in_progress": in_progress_count,
            "upcoming": upcoming_count,
        },
    }
    if index_path.exists():
        with index_path.open("r", encoding="utf-8") as handle:
            index = json.load(handle)
    else:
        index = {"history": []}
    history = index.setdefault("history", [])
    history = [item for item in history if item.get("date") != entry["date"]]
    history.append(entry)
    history.sort(key=lambda item: item["date"])
    index["history"] = history
    index["generated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("w", encoding="utf-8") as handle:
        json.dump(index, handle, indent=2)
        handle.write("\n")


def render_history(args: argparse.Namespace) -> HistoryDocument:
    repo = _determine_repo(args.repo)
    token = args.token or os.getenv("GITHUB_TOKEN")
    since = _parse_since(args.since)
    until = dt.datetime.now(dt.timezone.utc)

    LOGGER.info("Generating history for %s since %s", repo, since.isoformat())
    client = GithubClient(repo, token)

    try:
        closed_issues = client.list_closed_issues(since)
    except Exception as exc:  # noqa: BLE001 - surface to logs and continue
        LOGGER.warning("Failed to fetch closed issues: %s", exc)
        closed_issues = []
    try:
        merged_prs = client.list_merged_prs(since)
    except Exception as exc:  # noqa: BLE001 - surface to logs and continue
        LOGGER.warning("Failed to fetch merged PRs: %s", exc)
        merged_prs = []
    try:
        in_progress = client.list_open_issues_with_label(args.in_progress_label)
    except Exception as exc:  # noqa: BLE001 - surface to logs and continue
        LOGGER.warning("Failed to fetch in-progress issues: %s", exc)
        in_progress = []
    try:
        upcoming = client.list_open_issues_with_label(args.upcoming_label)
    except Exception as exc:  # noqa: BLE001 - surface to logs and continue
        LOGGER.warning("Failed to fetch upcoming issues: %s", exc)
        upcoming = []

    root = Path(args.root).resolve()
    notes = _collect_notes_and_decisions(root, since)
    notes.extend(_collect_jira_references(root, since))

    artifacts_enabled = args.enable_s3_artifacts or os.getenv(
        "HISTORIAN_ENABLE_S3_ARTIFACTS", "false"
    ).lower() == "true"
    artifacts: List[dict] = []
    if artifacts_enabled:
        artifacts_path = args.artifacts_file
        if not artifacts_path and (env_artifact := os.getenv("HISTORIAN_ARTIFACTS_FILE")):
            artifacts_path = Path(env_artifact)
        artifacts = _load_artifacts(artifacts_path)
    include_hash = args.include_hash or os.getenv("HISTORIAN_ENABLE_HASH", "false").lower() == "true"
    artifacts_section = _render_artifacts(artifacts, include_hash)

    completed_items = [_format_pr(pr) for pr in merged_prs] + [
        _format_issue(issue) for issue in closed_issues
    ]
    completed_section = _format_section(completed_items)
    in_progress_section = _format_section(_format_issue(issue) for issue in in_progress)
    upcoming_section = _format_section(_format_issue(issue) for issue in upcoming)
    notes_section = _format_section(notes)

    template_path = args.template
    if not template_path:
        template_path = root / "docs" / "history" / "HISTORY_TEMPLATE.md"
    with open(template_path, "r", encoding="utf-8") as handle:
        template = handle.read()

    context = {
        "date": until.date().isoformat(),
        "since": since.date().isoformat(),
        "until": until.date().isoformat(),
        "completed": completed_section.strip() or "_No updates_",
        "in_progress": in_progress_section.strip() or "_No updates_",
        "upcoming": upcoming_section.strip() or "_No updates_",
        "notes": notes_section.strip() or "_No updates_",
        "artifacts": artifacts_section.strip() or "_No artifacts recorded_",
    }

    for key, value in context.items():
        placeholder = "{{" + key + "}}"
        template = template.replace(placeholder, value)

    return HistoryDocument(
        markdown=template,
        since=since,
        until=until,
        completed_count=len(merged_prs) + len(closed_issues),
        in_progress_count=len(in_progress),
        upcoming_count=len(upcoming),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Git Historian check-in")
    parser.add_argument("--since", default="7d", help="Time window start (e.g. 7d, 24h, or ISO timestamp)")
    parser.add_argument("--output", default="docs/history", help="Directory to write the Markdown check-in")
    parser.add_argument("--repo", help="owner/name repository override")
    parser.add_argument("--token", help="GitHub API token (defaults to GITHUB_TOKEN)")
    parser.add_argument("--template", type=Path, help="Path to custom template")
    parser.add_argument("--artifacts-file", type=Path, help="JSON file describing artifacts")
    parser.add_argument("--include-hash", action="store_true", help="Include sha256 hashes in artifact output")
    parser.add_argument("--dry-run", action="store_true", help="Print the generated Markdown without writing")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root (defaults to current directory)",
    )
    parser.add_argument(
        "--in-progress-label",
        default="in-progress",
        help="Label used to identify in-progress issues",
    )
    parser.add_argument(
        "--upcoming-label",
        default="next-up",
        help="Label used to identify upcoming issues",
    )
    parser.add_argument(
        "--enable-s3-artifacts",
        action="store_true",
        help="Force-enable artifact rendering regardless of env flag",
    )

    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    root_path = Path(args.root).resolve()
    document = render_history(args)

    if args.dry_run:
        print(document.markdown)
        return

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{document.until.date().isoformat()}-checkin.md"
    output_path = output_dir / filename
    output_path.write_text(document.markdown, encoding="utf-8")
    LOGGER.info("Wrote %s", output_path)

    index_path = root_path / "docs" / "context" / "context-index.json"
    try:
        relative_output = output_path.resolve().relative_to(root_path)
    except ValueError:
        relative_output = output_path.resolve()
    _ensure_history_index(
        index_path,
        relative_output,
        document.since,
        document.until,
        document.completed_count,
        document.in_progress_count,
        document.upcoming_count,
    )


if __name__ == "__main__":
    main()

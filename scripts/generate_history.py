#!/usr/bin/env python3
"""Generate Release Copilot history check-ins with extended collectors."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import requests
import yaml

# Path safeguard for local/CI runs when PYTHONPATH is unset.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.github import ProjectsV2Client

LOGGER = logging.getLogger(__name__)
ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


@dataclass
class Issue:
    number: int
    title: str
    url: str
    closed_at: Optional[dt.datetime]
    assignees: List[str]
    labels: List[str]
    status: Optional[str] = None


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
    counts: Dict[str, int]


@dataclass
class SectionResult:
    entries: List[str]
    filters: List[str]
    metadata: Dict[str, object] = field(default_factory=dict)

    @property
    def count(self) -> int:
        return len(self.entries)


@dataclass
class NoteMarker:
    """Structured representation of a decision marker discovered in comments."""

    updated: dt.datetime
    marker: str
    detail: str
    status: Optional[str]
    number: int
    item_type: str
    url: Optional[str]
    author: Optional[str]
    comment_id: str
    line_index: int


class GithubClient:
    """Minimal GitHub REST API helper."""

    def __init__(
        self,
        repo: str,
        token: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.repo = repo
        self.base_url = f"https://api.github.com/repos/{repo}"
        self.session = session or requests.Session()
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "release-copilot-git-historian",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.session.headers.update(headers)

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        LOGGER.debug("%s %s params=%s", method, url, kwargs.get("params"))
        response = self.session.request(method, url, timeout=30, **kwargs)
        if response.status_code >= 400:
            raise RuntimeError(
                f"GitHub API error {response.status_code}: {response.text}"
            )
        return response

    def paginate(
        self,
        url: str,
        params: Optional[dict] = None,
        data_key: Optional[str] = None,
    ) -> Iterable[dict]:
        params = params.copy() if params else None
        while url:
            response = self._request("GET", url, params=params)
            data = response.json()
            if data_key is None:
                if isinstance(data, list):
                    items = data
                else:
                    raise RuntimeError(
                        f"Expected list response for {url}, received {type(data).__name__}"
                    )
            else:
                items = data.get(data_key, [])
            yield from items
            if "next" in response.links:
                url = response.links["next"]["url"]
                params = None
            else:
                break

    def list_closed_issues(self, since: dt.datetime, until: dt.datetime) -> List[Issue]:
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
            if closed_at and closed_at > until:
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

    def list_merged_prs(self, since: dt.datetime, until: dt.datetime) -> List[PullRequest]:
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
            if merged_at and merged_at > until:
                continue
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

    def list_issue_comments(self, since: dt.datetime) -> List[dict]:
        params = {
            "since": since.strftime(ISO_FORMAT),
            "per_page": 100,
        }
        return list(
            self.paginate(f"{self.base_url}/issues/comments", params)
        )

    def list_review_comments(self, since: dt.datetime) -> List[dict]:
        params = {
            "since": since.strftime(ISO_FORMAT),
            "per_page": 100,
        }
        return list(
            self.paginate(
                f"{self.base_url}/pulls/comments", params
            )
        )

    def get_issue(self, number: int) -> dict:
        response = self._request("GET", f"{self.base_url}/issues/{number}")
        return response.json()

    def list_workflow_runs(self, workflow: str) -> Iterable[dict]:
        params = {
            "per_page": 50,
            "status": "completed",
        }
        yield from self.paginate(
            f"{self.base_url}/actions/workflows/{workflow}/runs",
            params,
            data_key="workflow_runs",
        )

    def list_run_artifacts(self, run_id: int) -> List[dict]:
        response = self._request(
            "GET", f"{self.base_url}/actions/runs/{run_id}/artifacts"
        )
        data = response.json()
        return data.get("artifacts", [])


def _parse_since(value: str) -> dt.datetime:
    """Parse --since values such as ``7d`` or ISO timestamps."""

    if not value:
        raise ValueError("--since cannot be empty")

    value = value.strip()
    now = dt.datetime.now(dt.timezone.utc)

    if value.isdigit():
        raise ValueError(
            f"Invalid --since value '{value}'. Did you mean '{value}d'?"
        )

    if value.endswith("d") and value[:-1].isdigit():
        days = int(value[:-1])
        return now - dt.timedelta(days=days)
    if value.endswith("h") and value[:-1].isdigit():
        hours = int(value[:-1])
        return now - dt.timedelta(hours=hours)

    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            "Unable to parse --since value. Use relative formats like '7d' or '24h' "
            "or provide an ISO timestamp (e.g. 2024-12-31T00:00:00Z)."
        ) from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _parse_until(value: Optional[str]) -> dt.datetime:
    """Parse --until values accepting ISO timestamps or the literal 'now'."""

    if value is None:
        value = "now"

    value = value.strip()
    if not value or value.lower() == "now":
        return dt.datetime.now(dt.timezone.utc)

    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            "Unable to parse --until value. Use 'now' or an ISO timestamp (e.g. "
            "2024-12-31T00:00:00Z)."
        ) from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _validate_window(since: dt.datetime, until: dt.datetime) -> None:
    if since > until:
        raise ValueError("--since must be earlier than or equal to --until")


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


def _load_historian_config(config_path: Optional[Path], root: Path) -> Dict[str, object]:
    search_path = config_path or root / "config" / "defaults.yml"
    if not search_path.exists():
        raise FileNotFoundError(
            f"Historian configuration not found at {search_path.as_posix()}"
        )
    with search_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data.get("historian", {})


def _format_issue(issue: Issue, include_status: bool = False) -> str:
    assignees = f" (@{' @'.join(issue.assignees)})" if issue.assignees else ""
    status = f" — Status: {issue.status}" if include_status and issue.status else ""
    return f"- Issue [#{issue.number}]({issue.url}): {issue.title}{assignees}{status}"


def _format_pr(pr: PullRequest) -> str:
    author = f" by @{pr.author}" if pr.author else ""
    merged = pr.merged_at.strftime("%Y-%m-%d") if pr.merged_at else ""
    merged_suffix = f" (merged {merged})" if merged else ""
    return f"- PR [#{pr.number}]({pr.url}): {pr.title}{author}{merged_suffix}"


def _render_section(result: SectionResult, empty_message: str) -> str:
    if result.entries:
        return "\n".join(result.entries)
    lines = [f"_{line}_" for line in result.filters] if result.filters else []
    lines.append(empty_message)
    return "\n".join(lines)


def _collect_completed(
    merged_prs: Sequence[PullRequest],
    closed_issues: Sequence[Issue],
) -> SectionResult:
    entries = [_format_pr(pr) for pr in merged_prs]
    entries.extend(_format_issue(issue) for issue in closed_issues)
    filters = ["Scope: merged pull requests and closed issues in the window"]
    metadata = {
        "issue_numbers": {issue.number for issue in closed_issues},
        "pr_numbers": {pr.number for pr in merged_prs},
    }
    return SectionResult(entries=entries, filters=filters, metadata=metadata)


def _collect_project_section(
    owner: str,
    repo: str,
    client: GithubClient,
    projects_client: Optional[ProjectsV2Client],
    section_config: Dict[str, object],
    fallback_status: str,
) -> SectionResult:
    section_config = section_config or {}
    project_cfg = section_config.get("project_v2", {}) or {}
    labels = section_config.get("labels", []) or []
    filters: List[str] = []
    issue_map: Dict[int, Issue] = {}

    project_enabled = bool(project_cfg.get("enabled"))
    project_name = project_cfg.get("project_name") or ""
    status_field = project_cfg.get("status_field") or "Status"
    status_values = project_cfg.get("status_values", [fallback_status])

    if project_enabled:
        filters.append(
            f"Filters: Project '{project_name}' • {status_field} ∈ [{', '.join(status_values)}]"
        )
        if projects_client:
            try:
                project_items = projects_client.query_issues_with_status(
                    owner,
                    repo,
                    project_name,
                    status_field,
                    status_values,
                )
            except Exception as exc:  # noqa: BLE001 - log and rely on fallback
                LOGGER.warning(
                    "Projects v2 query failed for %s (%s): %s",
                    project_name,
                    fallback_status,
                    exc,
                )
                project_items = []
            for item in project_items:
                issue_map[item.number] = Issue(
                    number=item.number,
                    title=item.title,
                    url=item.url,
                    closed_at=None,
                    assignees=item.assignees,
                    labels=[],
                    status=item.status or fallback_status,
                )
        else:
            filters.append("Projects v2 lookup skipped (missing token)")
    else:
        filters.append("Projects v2 lookup disabled")

    if not issue_map and labels:
        for label in labels:
            try:
                for issue in client.list_open_issues_with_label(label):
                    issue.status = issue.status or fallback_status
                    issue_map.setdefault(issue.number, issue)
            except Exception as exc:  # noqa: BLE001 - log and continue
                LOGGER.warning("Label fallback failed for %s: %s", label, exc)
        filters.append(
            f"Scope: GitHub issues labeled {', '.join(labels)}"
        )
    elif project_enabled:
        filters.append("Scope: GitHub issues via Projects v2 board")
    elif labels:
        filters.append(
            f"Scope: GitHub issues labeled {', '.join(labels)}"
        )
    else:
        filters.append("Scope: No project or label filters configured")

    issues = sorted(issue_map.values(), key=lambda item: item.number)
    entries = [_format_issue(issue, include_status=True) for issue in issues]
    metadata = {"issue_status": {issue.number: issue.status or fallback_status for issue in issues}}
    return SectionResult(entries=entries, filters=filters, metadata=metadata)


def _extract_comment_markers(
    comments: Iterable[dict],
    markers: Sequence[str],
    status_lookup: Dict[Tuple[str, int], str],
    until: dt.datetime,
) -> List[NoteMarker]:
    results: List[NoteMarker] = []
    marker_prefixes = list(markers)
    for comment in comments:
        body = comment.get("body") or ""
        if not body:
            continue
        updated = _parse_github_datetime(
            comment.get("updated_at") or comment.get("created_at")
        )
        if not updated or updated > until:
            continue
        issue_url = comment.get("issue_url") or comment.get("pull_request_url")
        if not issue_url:
            continue
        try:
            number = int(issue_url.rsplit("/", 1)[-1])
        except ValueError:
            continue
        item_type = "pull_request" if comment.get("pull_request_url") else "issue"
        status = status_lookup.get((item_type, number)) or status_lookup.get(("issue", number))
        author = (comment.get("user") or {}).get("login")
        url = comment.get("html_url")
        comment_id = str(comment.get("id") or comment.get("node_id") or "")
        for index, line in enumerate(body.splitlines()):
            stripped = line.strip()
            if not stripped:
                continue
            for marker in marker_prefixes:
                if stripped.startswith(marker):
                    detail = stripped[len(marker) :].strip()
                    label = marker.rstrip(":")
                    results.append(
                        NoteMarker(
                            updated=updated,
                            marker=label,
                            detail=detail,
                            status=status,
                            number=number,
                            item_type=item_type,
                            url=url,
                            author=author,
                            comment_id=comment_id,
                            line_index=index,
                        )
                    )
    return results


def _format_note_entry(marker: NoteMarker, annotate_group: bool) -> str:
    if marker.detail:
        entry = f"- **{marker.marker}:** {marker.detail}"
    else:
        entry = f"- **{marker.marker}**"
    meta_parts: List[str] = []
    if annotate_group and marker.status:
        meta_parts.append(marker.status)
    link_target = marker.url or f"#{marker.number}"
    if marker.url:
        meta_parts.append(f"[#{marker.number}]({link_target})")
    else:
        meta_parts.append(link_target)
    if marker.author:
        meta_parts.append(f"@{marker.author}")
    meta_parts.append(marker.updated.strftime("%Y-%m-%d"))
    return entry + " — " + " · ".join(meta_parts)


def _collect_notes_section(
    client: GithubClient,
    notes_config: Dict[str, object],
    status_lookup: Dict[Tuple[str, int], str],
    since: dt.datetime,
    until: dt.datetime,
    root: Path,
    repo: str,
    mirror_config: Optional[Dict[str, object]] = None,
) -> SectionResult:
    notes_config = notes_config or {}
    markers = notes_config.get(
        "comment_markers", ["Decision:", "Note:", "Blocker:", "Action:"]
    )
    scan_issue_comments = notes_config.get("scan_issue_comments", True)
    scan_pr_comments = notes_config.get("scan_pr_comments", True)
    annotate_group = notes_config.get("annotate_group", True)
    scan_notes_files = notes_config.get("scan_notes_files", False)
    notes_glob = notes_config.get("notes_glob", "docs/history/notes/**/*.md")
    filters = [
        f"Markers: {', '.join(markers)}",
    ]
    scope_fragments = []
    if scan_issue_comments:
        scope_fragments.append("issues")
    if scan_pr_comments:
        scope_fragments.append("pull requests")
    filters.append(
        "Scope: comment bodies for " + (" & ".join(scope_fragments) if scope_fragments else "none")
    )
    if scan_notes_files:
        filters.append(f"Mirrored notes files: {notes_glob}")
    else:
        filters.append(f"Mirrored notes files: {notes_glob} (disabled)")

    marker_entries: List[NoteMarker] = []
    if markers:
        if scan_issue_comments:
            try:
                issue_comments = client.list_issue_comments(since)
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Failed to fetch issue comments: %s", exc)
                issue_comments = []
            marker_entries.extend(
                _extract_comment_markers(
                    issue_comments, markers, status_lookup, until
                )
            )
        if scan_pr_comments:
            try:
                review_comments = client.list_review_comments(since)
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Failed to fetch PR review comments: %s", exc)
                review_comments = []
            marker_entries.extend(
                _extract_comment_markers(
                    review_comments, markers, status_lookup, until
                )
            )
    else:
        LOGGER.debug("No markers configured for Notes & Decisions collector")

    local_notes = _collect_local_notes(root, since)
    jira_notes = _collect_jira_references(root, since)
    marker_entries.sort(key=lambda item: item.updated, reverse=True)
    formatted_markers = [
        _format_note_entry(marker, annotate_group) for marker in marker_entries
    ]
    note_entries = list(formatted_markers)
    note_entries.extend(local_notes)
    note_entries.extend(jira_notes)
    if marker_entries:
        _mirror_note_markers(
            client,
            repo,
            marker_entries,
            mirror_config or {},
            root,
            until.date(),
        )
    metadata = {"marker_entries": marker_entries}
    return SectionResult(entries=note_entries, filters=filters, metadata=metadata)


def _collect_local_notes(root: Path, since: dt.datetime) -> List[str]:
    notes: List[str] = []
    adr_dirs = [
        root / "docs" / "adr",
        root / "docs" / "adrs",
        root / "docs" / "decisions",
        root / "docs" / "architecture" / "adr",
    ]
    for adr_dir in adr_dirs:
        if adr_dir.exists():
            for path in sorted(
                adr_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True
            ):
                mtime = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
                if mtime < since:
                    continue
                rel = path.relative_to(root)
                notes.append(
                    f"- Updated ADR: [{path.stem}]({rel.as_posix()}) (modified {mtime.date()})"
                )
    return notes


def _collect_jira_references(root: Path, since: dt.datetime) -> List[str]:
    if os.getenv("HISTORIAN_ENABLE_JIRA", "false").lower() != "true":
        return []
    pattern = os.getenv("HISTORIAN_JIRA_REGEX", r"[A-Z]+-\d+")
    try:
        log_output = subprocess.check_output(
            ["git", "log", f"--since={since.isoformat()}", "--pretty=%H %s"],
            cwd=root,
        ).decode()
    except subprocess.CalledProcessError:
        LOGGER.warning("Failed to collect git log for Jira enrichment")
        return []
    regex = re.compile(pattern)
    references: Dict[str, List[str]] = {}
    for line in log_output.splitlines():
        if not line:
            continue
        commit, _, message = line.partition(" ")
        for match in regex.findall(message):
            references.setdefault(match, []).append(commit)
    items = []
    for key, commits in sorted(references.items()):
        commit_list = ", ".join(commit[:7] for commit in commits[:5])
        suffix = "" if len(commits) <= 5 else ", …"
        items.append(f"- Jira {key} linked to commits: {commit_list}{suffix}")
    return items


def _mirror_note_markers(
    client: GithubClient,
    repo: str,
    markers: Sequence[NoteMarker],
    mirror_config: Dict[str, object],
    root: Path,
    run_date: dt.date,
) -> None:
    if not markers:
        return
    if not mirror_config.get("enabled"):
        LOGGER.debug("Notes file mirroring disabled")
        return

    repo_root_cfg = mirror_config.get("repo_root", ".")
    output_dir_cfg = mirror_config.get("output_dir", "docs/history/notes")
    dry_run = bool(mirror_config.get("dry_run", False))
    annotate_group = mirror_config.get("annotate_group", True)

    base_path = Path(repo_root_cfg)
    if not base_path.is_absolute():
        base_path = (root / repo_root_cfg).resolve()
    notes_dir = Path(output_dir_cfg)
    if not notes_dir.is_absolute():
        notes_dir = (base_path / output_dir_cfg).resolve()
    else:
        notes_dir = notes_dir.resolve()

    if not dry_run:
        notes_dir.mkdir(parents=True, exist_ok=True)

    repo_slug = repo.replace("/", "-")
    issue_cache: Dict[int, dict] = {}
    digest_cache: Dict[Path, set[str]] = {}

    for marker in markers:
        note_path = notes_dir / f"{run_date.isoformat()}-{repo_slug}-{marker.number}.md"
        if note_path not in digest_cache:
            digest_cache[note_path] = _load_note_digests(note_path)
        digest = _compute_note_digest(repo, marker)
        if digest in digest_cache[note_path]:
            continue
        if dry_run:
            LOGGER.debug(
                "Dry run: would mirror note marker %s for #%s", digest, marker.number
            )
            continue
        issue_data = issue_cache.get(marker.number)
        if issue_data is None:
            try:
                issue_data = client.get_issue(marker.number)
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning(
                    "Failed to fetch metadata for #%s while mirroring notes: %s",
                    marker.number,
                    exc,
                )
                issue_data = {}
            issue_cache[marker.number] = issue_data
        _append_note_entry(
            note_path,
            repo,
            issue_data,
            marker,
            annotate_group,
            digest,
        )
        digest_cache[note_path].add(digest)


def _load_note_digests(path: Path) -> set[str]:
    if not path.exists():
        return set()
    content = path.read_text(encoding="utf-8")
    return set(re.findall(r"<!--\s*digest:([0-9a-f]{64})\s*-->", content))


def _compute_note_digest(repo: str, marker: NoteMarker) -> str:
    text_source = marker.detail or marker.marker
    text_hash = hashlib.sha256(text_source.encode("utf-8")).hexdigest()
    payload = "|".join(
        [repo, str(marker.number), marker.comment_id, str(marker.line_index), text_hash]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _default_item_url(repo: str, marker: NoteMarker) -> str:
    base = f"https://github.com/{repo}"
    if marker.item_type == "pull_request":
        return f"{base}/pull/{marker.number}"
    return f"{base}/issues/{marker.number}"


def _append_note_entry(
    path: Path,
    repo: str,
    issue_data: Dict[str, object],
    marker: NoteMarker,
    annotate_group: bool,
    digest: str,
) -> None:
    new_file = not path.exists()
    header_lines: List[str] = []
    if new_file:
        title = str(issue_data.get("title") or "").strip()
        header = f"# Notes & Decisions — #{marker.number}"
        if title:
            header += f" {title}"
        source_url = str(
            issue_data.get("html_url") or marker.url or _default_item_url(repo, marker)
        )
        header_lines = [
            header,
            "",
            f"_Repo:_ {repo}",
            f"_Source:_ {source_url}",
            "",
        ]

    status_label = marker.status or "Uncategorized"
    status_segment = f" ({status_label})" if annotate_group and status_label else ""
    author = f"@{marker.author}" if marker.author else "unknown"
    detail = (marker.detail or marker.marker).strip()
    if len(detail) > 300:
        detail = detail[:297].rstrip() + "…"
    comment_url = marker.url or str(
        issue_data.get("html_url") or _default_item_url(repo, marker)
    )

    entry_lines = [
        f"- {marker.marker}{status_segment} — {marker.updated.date().isoformat()} by {author}",
        f"  {detail}",
        f"  [View comment]({comment_url}) <!-- digest:{digest} -->",
    ]

    write_lines: List[str] = []
    if header_lines:
        write_lines.extend(header_lines)
    elif path.exists() and path.stat().st_size > 0:
        write_lines.append("")
    write_lines.extend(entry_lines)
    write_lines.append("")

    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(write_lines))

def _collect_github_actions_artifacts(
    client: GithubClient,
    workflows: Sequence[str],
    since: dt.datetime,
    until: dt.datetime,
) -> List[str]:
    entries: List[str] = []
    for workflow in workflows:
        try:
            runs = list(client.list_workflow_runs(workflow))
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to list workflow runs for %s: %s", workflow, exc)
            continue
        for run in runs:
            created = _parse_github_datetime(run.get("created_at"))
            if created and created < since:
                break
            if created and created > until:
                continue
            run_url = run.get("html_url")
            run_number = run.get("run_number") or run.get("id")
            try:
                artifacts = client.list_run_artifacts(run.get("id"))
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning(
                    "Failed to list artifacts for workflow %s run %s: %s",
                    workflow,
                    run_number,
                    exc,
                )
                continue
            for artifact in artifacts:
                created_at = _parse_github_datetime(artifact.get("created_at"))
                if created_at and created_at < since:
                    continue
                if created_at and created_at > until:
                    continue
                name = artifact.get("name", "artifact")
                expired = artifact.get("expired")
                download_url = artifact.get("archive_download_url")
                expires_at = _parse_github_datetime(artifact.get("expires_at"))
                status_parts = []
                if not expired and download_url:
                    status_parts.append(f"[download]({download_url})")
                if expired:
                    status_parts.append("expired")
                elif expires_at:
                    status_parts.append(f"expires {expires_at.date()}")
                status_suffix = f" ({', '.join(status_parts)})" if status_parts else ""
                entries.append(
                    f"- Workflow `{workflow}` run [#{run_number}]({run_url}) → **{name}**{status_suffix}"
                )
    return entries


def _collect_s3_artifacts(
    bucket: str,
    prefixes: Sequence[str],
    since: dt.datetime,
    until: dt.datetime,
) -> List[str]:
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover - boto3 should be available
        LOGGER.warning("boto3 is required for S3 artifact collection: %s", exc)
        return []

    client = boto3.client("s3")
    entries: List[str] = []
    for prefix in prefixes:
        continuation_token: Optional[str] = None
        while True:
            kwargs = {
                "Bucket": bucket,
                "Prefix": prefix,
                "MaxKeys": 1000,
            }
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token
            response = client.list_objects_v2(**kwargs)
            for obj in response.get("Contents", []):
                last_modified = obj.get("LastModified")
                if last_modified:
                    last_modified = last_modified.astimezone(dt.timezone.utc)
                    if last_modified < since or last_modified > until:
                        continue
                key = obj.get("Key")
                size = obj.get("Size")
                entries.append(
                    f"- S3 `{bucket}` → `{key}` ({size} bytes, updated {last_modified.date() if last_modified else 'unknown'})"
                )
            if not response.get("IsTruncated"):
                break
            continuation_token = response.get("NextContinuationToken")
    return entries


def _collect_artifacts_section(
    client: GithubClient,
    artifacts_config: Dict[str, object],
    since: dt.datetime,
    until: dt.datetime,
) -> SectionResult:
    artifacts_config = artifacts_config or {}
    filters: List[str] = []
    entries: List[str] = []

    gha_cfg = artifacts_config.get("github_actions", {}) or {}
    if gha_cfg.get("enabled"):
        workflows = gha_cfg.get("workflows", [])
        filters.append(
            "GitHub Actions workflows: " + (", ".join(workflows) if workflows else "all")
        )
        entries.extend(
            _collect_github_actions_artifacts(client, workflows, since, until)
        )
    else:
        filters.append("GitHub Actions workflows: disabled")

    s3_cfg = artifacts_config.get("s3", {}) or {}
    bucket = s3_cfg.get("bucket")
    prefixes = s3_cfg.get("prefixes", [])
    if s3_cfg.get("enabled") and bucket and prefixes:
        filters.append(
            f"S3 prefixes: s3://{bucket}/" + ", s3://{bucket}/".join(prefixes)
        )
        entries.extend(_collect_s3_artifacts(bucket, prefixes, since, until))
    elif bucket and prefixes:
        filters.append(
            f"S3 prefixes: s3://{bucket}/" + ", s3://{bucket}/".join(prefixes) + " (disabled)"
        )
    else:
        filters.append("S3 prefixes: disabled")

    return SectionResult(entries=entries, filters=filters)


def _ensure_history_index(
    index_path: Path,
    checkin_path: Path,
    since: dt.datetime,
    until: dt.datetime,
    counts: Dict[str, int],
) -> None:
    entry = {
        "date": until.date().isoformat(),
        "file": checkin_path.as_posix(),
        "since": since.isoformat(),
        "until": until.isoformat(),
        "counts": counts,
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
    until = _parse_until(getattr(args, "until", None))
    _validate_window(since, until)

    LOGGER.info(
        "Generating history for %s since %s until %s",
        repo,
        since.isoformat(),
        until.isoformat(),
    )
    client = GithubClient(repo, token)
    owner, _, name = repo.partition("/")
    if not owner or not name:
        raise ValueError(f"Invalid repository '{repo}'. Expected owner/name format.")

    root = Path(args.root).resolve()
    config = _load_historian_config(args.config, root)
    sources = config.get("sources", {})
    notes_mirror_cfg = config.get("notes_file_mirroring", {})
    in_progress_cfg = sources.get("in_progress", {})
    backlog_cfg = sources.get("backlog", {})
    notes_cfg = sources.get("notes", {})
    artifacts_cfg = sources.get("artifacts", {})

    try:
        closed_issues = client.list_closed_issues(since, until)
    except Exception as exc:  # noqa: BLE001 - surface to logs and continue
        LOGGER.warning("Failed to fetch closed issues: %s", exc)
        closed_issues = []
    try:
        merged_prs = client.list_merged_prs(since, until)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Failed to fetch merged PRs: %s", exc)
        merged_prs = []

    completed_result = _collect_completed(merged_prs, closed_issues)

    projects_client: Optional[ProjectsV2Client] = None
    try:
        if token and (
            (in_progress_cfg.get("project_v2", {}).get("enabled"))
            or (backlog_cfg.get("project_v2", {}).get("enabled"))
        ):
            projects_client = ProjectsV2Client(token)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Failed to initialize Projects v2 client: %s", exc)

    in_progress_result = _collect_project_section(
        owner,
        name,
        client,
        projects_client,
        in_progress_cfg,
        fallback_status="In Progress",
    )
    backlog_result = _collect_project_section(
        owner,
        name,
        client,
        projects_client,
        backlog_cfg,
        fallback_status="Backlog",
    )

    status_lookup: Dict[Tuple[str, int], str] = {}
    status_lookup.update({("issue", num): "Completed" for num in completed_result.metadata.get("issue_numbers", set())})
    status_lookup.update({("pull_request", num): "Completed" for num in completed_result.metadata.get("pr_numbers", set())})
    for number, status in in_progress_result.metadata.get("issue_status", {}).items():
        status_lookup[("issue", number)] = status or "In Progress"
    for number, status in backlog_result.metadata.get("issue_status", {}).items():
        status_lookup[("issue", number)] = status or "Backlog"

    notes_result = _collect_notes_section(
        client,
        notes_cfg,
        status_lookup,
        since,
        until,
        root,
        repo,
        notes_mirror_cfg,
    )
    artifacts_result = _collect_artifacts_section(
        client,
        artifacts_cfg,
        since,
        until,
    )

    template_path = args.template or root / "docs" / "history" / "HISTORY_TEMPLATE.md"
    with open(template_path, "r", encoding="utf-8") as handle:
        template = handle.read()

    context = {
        "date": until.date().isoformat(),
        "since": since.date().isoformat(),
        "until": until.date().isoformat(),
        "completed": _render_section(
            completed_result, "_No completed work in this window_"
        ),
        "in_progress": _render_section(
            in_progress_result,
            "_No matching in-progress issues (see filters above)_",
        ),
        "backlog": _render_section(
            backlog_result, "_No matching backlog issues (see filters above)_"
        ),
        "notes": _render_section(
            notes_result,
            "_No decision markers captured in this window_",
        ),
        "artifacts": _render_section(
            artifacts_result, "_No artifacts captured in this window_"
        ),
        "completed_count": str(completed_result.count),
        "in_progress_count": str(in_progress_result.count),
        "backlog_count": str(backlog_result.count),
        "notes_count": str(notes_result.count),
        "artifacts_count": str(artifacts_result.count),
    }

    for key, value in context.items():
        placeholder = "{{" + key + "}}"
        template = template.replace(placeholder, value)

    counts = {
        "completed": completed_result.count,
        "in_progress": in_progress_result.count,
        "backlog": backlog_result.count,
        "notes": notes_result.count,
        "artifacts": artifacts_result.count,
    }
    return HistoryDocument(markdown=template, since=since, until=until, counts=counts)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Git Historian check-in")
    parser.add_argument(
        "--since",
        default="7d",
        help=(
            "Relative format like '7d'/'24h' or ISO timestamp "
            "(YYYY-MM-DDTHH:MM:SSZ)"
        ),
    )
    parser.add_argument(
        "--until",
        help="Time window end (ISO timestamp or 'now'; defaults to now)",
    )
    parser.add_argument(
        "--output",
        default="docs/history",
        help="Directory to write the Markdown check-in",
    )
    parser.add_argument("--repo", help="owner/name repository override")
    parser.add_argument("--token", help="GitHub API token (defaults to GITHUB_TOKEN)")
    parser.add_argument("--template", type=Path, help="Path to custom template")
    parser.add_argument("--config", type=Path, help="Path to historian YAML configuration")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the generated Markdown without writing",
    )
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root (defaults to current directory)",
    )

    return parser


def main() -> None:
    parser = _build_parser()
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
    _ensure_history_index(index_path, relative_output, document.since, document.until, document.counts)


if __name__ == "__main__":
    main()

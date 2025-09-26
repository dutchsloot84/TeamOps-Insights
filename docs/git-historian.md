# Git Historian (How to Run)

The Git Historian generates weekly (and on-demand) check-ins that summarize project momentum for Release Copilot.
This guide explains how to run the generator locally, how the scheduled GitHub Action works, and how to customize the
output for your team.

## Prerequisites

* Python 3.10+
* `requests` (installed automatically when you run `pip install -r requirements.txt`)
* A GitHub token with `repo` scope when running outside GitHub Actions. Export it as `GITHUB_TOKEN`.
* Optional integrations:
  * Set `HISTORIAN_ENABLE_JIRA=true` with relevant Jira credentials for linking stories to commits.
  * Provide AWS credentials (via environment or profile) when enabling the S3 artifact collector in `config/defaults.yml`.

## Running Locally

```bash
# Activate your virtual environment and install dependencies if needed
pip install -r requirements.txt

# Generate a history snapshot from the last 7 days
export GITHUB_TOKEN=<your-token>
export PYTHONPATH=$(pwd)
python -m scripts.generate_history --since 7d --until now --output docs/history --debug-scan
```

* The script creates `docs/history/YYYY-MM-DD-checkin.md` using [`docs/history/HISTORY_TEMPLATE.md`](history/HISTORY_TEMPLATE.md).
* Use `--debug-scan` to automatically enable DEBUG logging and emit additional scan diagnostics (counts, resolved paths).
  Pass `--log-level` if you need a different verbosity.
* Use `--since` with ISO timestamps (`2025-01-01T00:00:00Z`) or relative windows (`14d`, `48h`).
* Use `--until now` (default) or a specific ISO timestamp (`2025-01-15`) to cap the window end.
* Use `--repo owner/name` to override automatic repository detection.
* Use `--config <path>` to load a different historian configuration (defaults to `config/defaults.yml`).
* **Tip:** If you see `ModuleNotFoundError: No module named 'scripts'`, confirm you are running from the repository root and that `PYTHONPATH` includes the root (e.g., `export PYTHONPATH=$(pwd)`).

### Collector overview

Git Historian renders five sections from a single run:

| Section | Source | Notes |
| --- | --- | --- |
| **Completed** | Merged pull requests + closed issues in the time window | Counted once per item. |
| **In Progress** | GitHub Projects v2 (status filter) with optional label fallback | Configure the project title, status field, and allowed values in `config/defaults.yml`. |
| **Backlog** | GitHub Projects v2 (status filter) | Uses the same query mechanism as In Progress. |
| **Notes & Decisions** | Issue + PR comments containing configured markers | Each matching line is annotated with its parent item's status (Completed/In Progress/Backlog). |
| **Artifacts & Traceability** | GitHub Actions artifacts + optional S3 prefixes | Requires workflow names in the config; S3 listing is disabled by default. |

Each collector contributes metadata (filters and scope) that is shown whenever a section has no entries.

## GitHub Action (Scheduled + Manual)

The workflow in [`.github/workflows/weekly-history.yml`](../.github/workflows/weekly-history.yml) runs every Monday at 14:00 UTC
and can also be triggered manually (`workflow_dispatch`). It performs the following steps:

1. Check out the repository.
2. Lint the GitHub workflow definitions with [`reviewdog/action-actionlint`](https://github.com/reviewdog/action-actionlint)
   pinned to commit `93dc1f9bc10856298b6cc1a3b3239cfbbb87fe4b` (release `v1.67.0`) and `fail_level: error`
   so any detected issues fail fast.
3. Run `PYTHONPATH=$(pwd) python -m scripts.generate_history --since 7d --until now --output docs/history --debug-scan`.
4. Commit changes in `docs/history/*.md` on a branch named `auto/history-<date>`.
5. Open a pull request summarizing the update.

If no files change, the workflow exits early and does not create a PR.

To run the workflow manually:

1. Navigate to **Actions → Weekly Git Historian** in GitHub.
2. Click **Run workflow** and optionally override the `since` window or template path.
3. A pull request is created automatically if new history content is generated.

### Linting and maintenance

* The workflow lint step relies on `reviewdog/action-actionlint` pinned to commit
  `93dc1f9bc10856298b6cc1a3b3239cfbbb87fe4b` (release `v1.67.0`). Update to a newer
  version by editing the `uses:` line in the workflow to a newer commit SHA and adjusting
  this document.
* The action runs `actionlint` against files in `.github/workflows/`. If lint errors are
  reported, the job fails and the check run contains the detailed findings.
* When bumping the version, use `curl https://api.github.com/repos/reviewdog/action-actionlint/releases`
  (or the GitHub UI) to select the desired release, copy the commit SHA, and update the
  workflow `uses:` reference.
* If the GitHub Actions runner cannot resolve the action due to registry outages, fall back
  to [installing the binary directly](https://github.com/rhysd/actionlint#download) in a shell
  step. Add a TODO comment in the workflow and revert once the marketplace issue is resolved.

## Customization

* **Template** – Pass `--template <path>` to the script to point to a custom Markdown template.
* **Collectors** – Edit `config/defaults.yml` (or pass `--config`) to adjust Projects v2 filters, comment markers, workflow names, and S3 prefixes.
* **Jira Linkage** – When `HISTORIAN_ENABLE_JIRA=true` and Jira credentials are configured, issues matching the configured
  JQL query are matched to commits using a regex (default: `[A-Z]+-\d+`). See the script docstring for configuration details.
* **Artifacts** – GitHub Actions artifacts are fetched using the configured workflow file names. Enable the S3 section in the config to add bucket prefixes.
* **Dry Runs** – Use `--dry-run` to print the generated Markdown to stdout without writing a file.

## Troubleshooting

* Ensure `GITHUB_TOKEN` is available; unauthenticated calls are heavily rate limited.
* Use `--debug-scan` (or `--log-level DEBUG`) for verbose output when debugging API calls or data collectors.
* If you rely on Jira, confirm the `HISTORIAN_JIRA_*` variables are set and the JQL matches your workflow.
* Customize the schedule in the workflow by editing the cron expression in `weekly-history.yml`.

## Next Steps

* Link the generated check-ins from your Release Copilot dashboards or onboarding docs.
* Extend the generator to publish artifacts to S3 and enable the S3 collector in `config/defaults.yml`.
* Use the machine-readable index at `docs/context/context-index.json` (generated by the script) to support RAG pipelines.

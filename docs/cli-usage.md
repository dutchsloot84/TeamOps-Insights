# CLI Usage

Release Copilot exposes a subcommand-oriented CLI under the `rc` entry point. The
first supported workflow, `rc audit`, rebuilds release audit artifacts entirely
from cached Jira and Bitbucket payloads. This keeps the pipeline deterministic
and enables teams to reproduce historical audits without hitting live APIs.

```bash
rc audit \
  --cache-dir temp_data \
  --json dist/audit.json \
  --xlsx dist/audit.xlsx \
  --scope fixVersion=2025.09.20
```

The command reads cached payloads from `temp_data/`, generates JSON and Excel
artifacts in `dist/`, and records the fix version in the execution scope. The
scope is included in structured logs and S3 metadata to support Historian
traceability.

## Defaults and configuration

Both the CLI and the Lambda entry points rely on the shared defaults loader in
[`src/config/loader.py`](../src/config/loader.py). The loader resolves the
project root, cache directory, artifact directory, and reports directory by
looking at environment overrides first and falling back to conventional
locations:

- `RC_ROOT` → project root (default: repository root)
- `RC_CACHE_DIR` → cached payloads (default: `<root>/temp_data`)
- `RC_ARTIFACT_DIR` → generated artifacts (default: `<root>/dist`)
- `RC_REPORTS_DIR` → published reports (default: `<root>/reports`)

The loader also exposes the default export formats (`json,excel`). These values
are injected into the `rc audit` execution plan to keep the CLI and the Lambda
in sync.

## Command reference

| Flag | Description |
| ---- | ----------- |
| `--cache-dir` | Directory containing the cached JSON payloads required for exports. |
| `--json` | Destination path for the regenerated JSON artifact. |
| `--xlsx` | Destination path for the regenerated Excel workbook. |
| `--summary` | Destination path for the summary JSON payload. |
| `--scope` | Repeatable `key=value` metadata entries describing the audit scope. |
| `--upload` | Optional S3 URI (`s3://bucket/prefix`) to receive the generated artifacts. |
| `--region` | AWS region used for uploads (defaults to `AWS_REGION`/`AWS_DEFAULT_REGION`). |
| `--dry-run` | Print the execution plan and exit without touching the filesystem. |
| `--log-level` | Logging verbosity (`INFO` by default). |

Pass `--dry-run` to validate paths, scope metadata, and upload destinations. The
command returns a JSON payload describing the planned outputs without reading or
writing files. This is useful for CI pipelines where you want to confirm the
execution plan before mounting caches.

## Cached payload expectations

`rc audit` expects four JSON files in the cache directory:

- `stories.json` → stories without commits
- `commits.json` → orphan commit payloads
- `links.json` → commit-to-story mappings
- `summary.json` → aggregated metrics

These files are produced by the data collection phases of the legacy pipeline
and retained by Historian. Missing or corrupt payloads cause the command to exit
with a helpful error explaining which file needs to be recovered.

If the cache is available but the original export step failed, use
[`recover_and_export.py`](../recover_and_export.py) as a convenience wrapper.
It calls the same exporter under the hood but accepts separate knobs for
selecting formats.

## Uploading artifacts to S3

When `--upload` is provided, the CLI stages the generated artifacts in a
temporary directory and calls `releasecopilot.uploader.upload_directory` to push
them to Amazon S3. Each object is encrypted with SSE-S3 and tagged with:

- `artifact=rc-audit`
- `scope=<JSON encoded scope>`

This mirrors the Lambda metadata and makes it straightforward for Historian to
associate uploads with a specific audit scope.

## Logging

Log messages use the shared configuration in
[`releasecopilot.logging_config`](../src/releasecopilot/logging_config.py). Scope
metadata is included in structured log fields, while secret values remain
redacted thanks to the existing logging filters.

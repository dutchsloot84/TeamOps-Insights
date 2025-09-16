# releasecopilot-ai

Releasecopilot AI automates release audits by correlating Jira stories with Bitbucket commits and exporting structured reports. The project ships with a modular Python codebase, Docker packaging, and AWS primitives for Lambda or container-based execution.

## Features

- Fetch Jira issues for a given fix version using OAuth 3LO tokens.
- Retrieve Bitbucket Cloud commits for configurable repositories and branches.
- Detect stories without commits and commits without linked stories.
- Export release audit results to JSON and Excel files.
- Persist raw API payloads for historical analysis and resume support.
- Upload artifacts to Amazon S3 and leverage Secrets Manager for credentials.
- Ready for container deployment or invocation via AWS Lambda.

## Project Layout

```
releasecopilot-ai/
├── main.py
├── clients/
├── processors/
├── exporters/
├── aws/
├── config/
├── data/
├── temp_data/
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

- **clients/** – API integrations for Jira, Bitbucket, and secret retrieval.
- **processors/** – Business logic to correlate stories and commits.
- **exporters/** – JSON and Excel exporters for the audit report.
- **aws/** – Lambda entry point and S3 helpers.
- **config/** – YAML configuration including AWS and workspace defaults.
- **data/** – Final audit outputs.
- **temp_data/** – Cached raw API responses for resuming and auditing.

## Prerequisites

- Python 3.11+
- Access to Jira Cloud with OAuth 3LO configured.
- Bitbucket Cloud workspace access (OAuth token or username + app password).
- Optional AWS account with permissions for Secrets Manager and S3.

Install Python dependencies locally:

```bash
pip install -r requirements.txt
```

## Configuration

1. Copy `.env` and populate the placeholders with local credentials (optional when using AWS Secrets Manager).
2. Update `config/settings.yaml` with your Jira site URL, Bitbucket workspace, and AWS resource names.
3. Store production credentials in AWS Secrets Manager using JSON keys that match the environment variable names (e.g., `JIRA_CLIENT_ID`, `BITBUCKET_APP_PASSWORD`).

## CLI Usage

Run the audit locally:

```bash
python main.py \
  --fix-version 2025.09.20 \
  --repos policycenter claimcenter \
  --develop-only \
  --upload-s3
```

### Available Options

| Flag | Description |
| ---- | ----------- |
| `--fix-version` | Release fix version (required). |
| `--repos` | One or more Bitbucket repository slugs to inspect. |
| `--branches` | Optional list of branches (defaults to config). |
| `--develop-only` | Convenience flag equivalent to `--branches develop`. |
| `--freeze-date` | ISO date representing the code freeze (default: today). |
| `--window-days` | Days of history to analyze before the freeze date (default: 28). |
| `--use-cache` | Reuse the latest cached API payloads instead of calling APIs. |
| `--upload-s3` | Upload generated artifacts to S3 after completion. |
| `--s3-bucket` | Override the S3 bucket defined in `config/settings.yaml`. |
| `--s3-prefix` | Prefix within the S3 bucket for uploaded artifacts. |
| `--output-prefix` | Basename for generated output files. |

## AWS Deployment

### Lambda

1. Build the container image:
   ```bash
   docker build -t releasecopilot-ai .
   ```
2. Push the image to Amazon ECR and create a Lambda function using the image.
3. Provide an execution role with access to:
   - AWS Secrets Manager (for Jira/Bitbucket credentials)
   - Amazon S3 (for storing artifacts)
   - CloudWatch Logs (for observability)
4. Invoke the function with a payload similar to [`aws/event_example.json`](aws/event_example.json).

### ECS/Fargate or Batch

Use the provided `Dockerfile` and pass CLI arguments through task definitions or AWS Batch job parameters. Mount or sync `/data` and `/temp_data` to S3 as part of the workflow if persistent storage is required.

## Secrets Management

- At runtime the application first checks environment variables, then AWS Secrets Manager.
- Secrets should be stored as JSON maps, for example:
  ```json
  {
    "JIRA_CLIENT_ID": "...",
    "JIRA_CLIENT_SECRET": "...",
    "JIRA_ACCESS_TOKEN": "...",
    "JIRA_REFRESH_TOKEN": "...",
    "JIRA_TOKEN_EXPIRY": 1700000000
  }
  ```
- Bitbucket secrets can include either an OAuth access token or a username/app-password pair.

## Outputs

- `data/jira_issues.json` – Jira issues retrieved for the fix version.
- `data/bitbucket_commits.json` – Commits fetched from Bitbucket.
- `data/<prefix>.json` – Structured audit report.
- `data/<prefix>.xlsx` – Multi-tab Excel workbook with summary, gaps, and mapping.

Artifacts are also uploaded to S3 when `--upload-s3` is supplied.

## Docker Compose

To iterate quickly with local services:

```bash
docker-compose run --rm releasecopilot \
  --fix-version 2025.09.20 \
  --repos policycenter claimcenter \
  --develop-only
```

## Logging

Logs are emitted in JSON-friendly format, making them CloudWatch-ready. Adjust log levels through the `LOG_LEVEL` environment variable (defaults to `INFO`).

## Testing & Contribution

- Linting and unit tests can be wired into GitHub Actions as part of CI/CD.
- `temp_data/` retains every raw response; purge periodically if storage becomes large.
- Contributions should include updates to this README when adding new functionality.

## Documentation

Published with MkDocs Material (auto-deployed from `main`):
https://<your-github-username>.github.io/releasecopilot-ai

Edit pages under `docs/` and push to `main` — the site republish is automated by GitHub Actions.

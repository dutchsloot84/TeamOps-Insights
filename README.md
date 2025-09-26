# releasecopilot-ai

Releasecopilot AI automates release audits by correlating Jira stories with Bitbucket commits and exporting structured reports. The project ships with a modular Python codebase, Docker packaging, and AWS primitives for Lambda or container-based execution.

> **Weekly Git Historian:** Our scheduled [`weekly-history`](.github/workflows/weekly-history.yml) workflow lints the repository's
> GitHub Actions definitions with `actionlint` and publishes momentum snapshots every Monday at 14:00 UTC. Trigger it manually
> from the **Actions** tab to generate an on-demand report.

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

Optional helpers (such as loading a local `.env` file) live in
`requirements-optional.txt`:

```bash
pip install -r requirements-optional.txt
```

## Configuration

1. Copy `.env.example` to `.env` for local development and populate the placeholders with test credentials. The file is `.gitignore`d—keep real secrets out of version control.
2. Install the optional dependency with `pip install -r requirements-optional.txt` to enable automatic loading of the `.env` file.
3. Update `config/settings.yaml` with your Jira site URL, Bitbucket workspace, and AWS resource names.
4. Store production credentials in AWS Secrets Manager using JSON keys that match the environment variable names (e.g., `JIRA_CLIENT_ID`, `BITBUCKET_APP_PASSWORD`).

Configuration precedence is:

1. CLI flags (highest priority)
2. Environment variables, including values sourced from `.env`
3. YAML defaults (`releasecopilot.yaml`)

For non-local deployments, rely on AWS Secrets Manager wherever possible and only fall back to `.env` for iterative development.

## CLI Usage

Run the audit locally:

```bash
python main.py \
  --fix-version 2025.09.20 \
  --repos policycenter claimcenter \
  --develop-only \
  --s3-bucket my-artifacts-bucket \
  --s3-prefix audits
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
| `--s3-bucket` | Override the S3 bucket defined in `config/settings.yaml`. |
| `--s3-prefix` | Prefix within the S3 bucket for uploaded artifacts (default: `releasecopilot`). |
| `--output-prefix` | Basename for generated output files. |

### S3 Upload Layout

When an S3 bucket is configured via CLI, configuration, or environment variables,
the audit automatically uploads generated artifacts after a successful run. The
files are grouped by fix version and execution timestamp using the pattern:

```
s3://<bucket>/<prefix>/<fix-version>/<YYYY-MM-DD_HHMMSS>/
├── reports/
│   ├── <output-prefix>.json
│   ├── <output-prefix>.xlsx
│   └── summary.json
└── raw/
    ├── jira_issues.json
    └── bitbucket_commits.json
```

Each object is encrypted with SSE-S3 and tagged with metadata that captures the
fix version, generation timestamp, and the current Git SHA when available.

## Streamlit Dashboard

Explore generated audit reports with the bundled Streamlit UI. The app can open
local JSON outputs or browse reports hosted in Amazon S3.

### Running the app

```bash
streamlit run ui/app.py
```

### Local reports

1. Point the "Reports folder" sidebar field to a directory containing the
   exported `*.json` and (optionally) `*.xlsx` files. The most recent JSON file
   is loaded automatically.
2. A sample fixture is provided at `reports/sample.json` for quick exploration.

### Amazon S3 mode

1. Ensure AWS credentials are available to the process (`AWS_ACCESS_KEY_ID`,
   `AWS_SECRET_ACCESS_KEY`, and `AWS_REGION` or a configured profile).
2. Enter the bucket name and optional prefix. The dashboard lists runs grouped
   by fix version and execution date. Selecting a run downloads the JSON report
   and offers a presigned link to the Excel workbook when available.

The main view surfaces KPI metrics, filters (fix version, status, assignee,
labels/components, repository, branch, and commit date range), and tables for
stories with commits, stories without commits, and orphan commits. Filtered
tables can be exported as CSV files. A comparison mode allows diffing the
current run against a previous report and integrates with the `#24` diff API via
an optional endpoint field.

## CI pipeline

Every push or pull request that targets `main` or any `feature/*` branch runs the
baseline GitHub Actions workflow defined in [`.github/workflows/ci.yml`](.github/workflows/ci.yml).
The pipeline provisions Python 3.11, installs both the runtime and development
dependencies, runs focused Ruff lint checks (syntax and runtime errors) and the
pytest suite, and invokes the existing packaging helper to build the Lambda
bundle. A follow-up job ensures the infrastructure code synthesises by running
`cdk synth` from `infra/cdk` with the AWS CDK CLI. When a tag matching
`v*.*.*` is pushed, the packaged `lambda_bundle.zip` artifact is uploaded to the
run for download.

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

### Deploying to AWS (per environment)

Infrastructure for the audit workflow is defined in `infra/cdk`. Each AWS environment is described by a small JSON/YAML file in `infra/envs/` (examples: [`dev.json`](infra/envs/dev.json), [`prod.json`](infra/envs/prod.json)). The file controls bucket naming, secret names, schedule settings, and other CDK context values.

1. Install the CDK dependencies once:
   ```bash
   pip install -r infra/cdk/requirements.txt
   ```
2. Review or create `infra/envs/<env>.json` with your desired settings. `bucketBase` and `secrets` must be provided.
3. Deploy using the helper script:
   ```bash
   python scripts/deploy_env.py --env dev --package
   ```
   - `--package` ensures `scripts/package_lambda.sh` runs before deployment so the Lambda artifact is up to date.
   - Add `--no-schedule` to disable the optional EventBridge rule regardless of the environment config.
4. The script bootstraps the account if needed (`cdk bootstrap`) and then executes `cdk deploy --require-approval never` with the environment context derived from the configuration file.

### Synth prerequisites

`infra/cdk/app.py` automatically works out the deployment account and region, but `cdk synth` still needs one of the following to succeed:

1. **CDK context:** supply `account`/`region` in `infra/cdk/cdk.json`, an `infra/envs/<env>.json` file, or via CLI flags, e.g. `cdk synth -c account=123456789012 -c region=us-west-2`.
2. **AWS credentials:** run `aws configure`, `aws sso login`, or export environment variables so that `boto3` can call `sts:GetCallerIdentity`. The resolved identity is used for the CDK environment automatically.
3. **Explicit environment variables:** export `CDK_DEFAULT_ACCOUNT` (and optionally `CDK_DEFAULT_REGION`) before invoking `cdk synth`.

Any of the above options keeps local developer workflows working while ensuring CI has enough information to synthesise the stacks.

Production buckets are retained by default; set `"retainBucket": false` in non-production configs to allow destruction on stack deletion.

## Secrets Management

- At runtime the application evaluates configuration in the following order: CLI flags → environment variables (including a local `.env` when present) → YAML defaults. When enabled, AWS Secrets Manager still acts as the fallback for secrets that remain unset.
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
- `.env` files are intended for local experiments only—use AWS Secrets Manager for shared or deployed environments.

## Outputs

- `data/jira_issues.json` – Jira issues retrieved for the fix version.
- `data/bitbucket_commits.json` – Commits fetched from Bitbucket.
- `data/<prefix>.json` – Structured audit report.
- `data/<prefix>.xlsx` – Multi-tab Excel workbook with summary, gaps, and mapping.

Artifacts are automatically uploaded to Amazon S3 whenever a bucket is configured via `--s3-bucket` (or the corresponding
configuration/env setting). Use `--s3-prefix` to control the destination prefix.

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

### Deploying with CDK (dev)

```bash
cd infra/cdk
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\Activate
pip install -r requirements.txt
cdk bootstrap
pytest -q
cdk synth
cdk deploy --require-approval never

# override context if needed
cdk deploy   --context bucketBase=releasecopilot-artifacts   --context jiraSecretArn=arn:aws:secretsmanager:...   --context bitbucketSecretArn=arn:aws:secretsmanager:...
```

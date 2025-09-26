# CLI Usage

Release Copilot ships with a single entry point (`main.py`) that reads defaults
from [`config/settings.yaml`](../config/settings.yaml). Configuration values are
merged at runtime using the following precedence:

1. Command line arguments (highest priority)
2. Environment variables, including values loaded from a local `.env`
3. YAML defaults defined in `config/settings.yaml`

Secrets such as Jira or Bitbucket credentials follow a similar order inside the
`CredentialStore` helper:

1. Environment variables (or values provided in a `.env` file)
2. AWS Secrets Manager payloads referenced by `aws.secrets.*`
3. YAML defaults in `config/settings.yaml`

## Running the CLI

```bash
python main.py \
  --fix-version 2025.09.27 \
  --repos policycenter claimcenter \
  --use-cache
```

The command above overrides the repositories configured in `config/settings.yaml`
and forces the CLI to reuse cached API payloads. Any flag supplied on the
command line supersedes environment variables and file-based defaults.

## Available options

| Flag | Description |
| ---- | ----------- |
| `--fix-version` | Release fix version (required). |
| `--repos` | One or more Bitbucket repository slugs to inspect. |
| `--branches` | Optional list of branches (defaults to configuration). |
| `--develop-only` | Convenience flag equivalent to `--branches develop`. |
| `--freeze-date` | ISO date representing the code freeze (default: today). |
| `--window-days` | Days of history to analyze before the freeze date (default: 28). |
| `--use-cache` | Reuse the latest cached API payloads instead of calling APIs. |
| `--s3-bucket` | Override the S3 bucket defined in `config/settings.yaml`. |
| `--s3-prefix` | Prefix within the S3 bucket for uploaded artifacts (default: `releasecopilot`). |
| `--output-prefix` | Basename for generated output files. |
| `--log-level` | Logging verbosity for the current run. |

## Providing secrets

Provide secrets through environment variables (for example `JIRA_CLIENT_SECRET`
or `BITBUCKET_APP_PASSWORD`). If a value is missing, the CLI looks for an AWS
Secrets Manager secret whose ARN is defined under `aws.secrets.jira` or
`aws.secrets.bitbucket` in `config/settings.yaml`. The secret payload must expose
keys that match the expected environment variable names. When neither source has
a value, the CLI falls back to the YAML defaults.

## Recovery Mode

If the main pipeline completes its data collection phase but fails before
exporting artifacts, you can rebuild the outputs from the cached JSON files
using `recover_and_export.py`. The tool reads the intermediate payloads stored
in `temp_data/` and produces the same Excel workbook and JSON summary generated
by the normal export stage.

```bash
python recover_and_export.py --input-dir temp_data --format excel
```

The command above regenerates only the Excel workbook in the default output
directory `reports/`. By default the utility writes both `audit_results.xlsx`
and `audit_results.json` (alongside `summary.json`) to the selected output
folder, mirroring the filenames created by the primary CLI.

## Loading local secrets

For local runs you can populate a `.env` file and let the CLI source values from
it. Copy the template and install the optional dependency:

```bash
cp .env.example .env
pip install -r requirements-optional.txt
```

Populate the placeholders with development credentials and keep `.env` out of
version control (the file is already ignored by git). In deployed environments
prefer AWS Secrets Manager and use `.env` only for local iteration.

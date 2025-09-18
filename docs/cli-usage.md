# CLI Usage

The Release Copilot CLI accepts configuration from YAML files, environment variables, and direct flags. Configuration precedence is:

1. Command line arguments (highest priority)
2. Environment variables
3. YAML defaults (`releasecopilot.yaml`)

Secrets follow the same order, and when `--use-aws-secrets-manager` is provided the CLI falls back to AWS Secrets Manager for any missing values. Secrets retrieved from AWS are cached so that each key is only fetched once per run.

## Running the CLI

```bash
python main.py --config releasecopilot.yaml --fix-version 2025.09.27
```

Any CLI flag can override both environment variables and YAML defaults. For example, set `JIRA_BASE` in your environment but override it for a one-off run using `--jira-base`.

## Providing Secrets

Provide secrets through CLI flags (e.g., `--jira-token`, `--bitbucket-token`) or matching environment variables (`JIRA_TOKEN`, `BITBUCKET_TOKEN`). If a secret is still missing and AWS fallback is enabled, Release Copilot will request the value from AWS Secrets Manager using the same key name.

To enable the fallback, pass `--use-aws-secrets-manager` or set the environment variable `USE_AWS_SECRETS_MANAGER=true`.

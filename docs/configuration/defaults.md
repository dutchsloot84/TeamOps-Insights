# Configuration defaults

`config/defaults.yml` is the canonical source of configuration for Release Copilot.
Both the CLI (`main.py`) and the Lambda entry point resolve their runtime settings
through the shared loader in `src/config/loader.py`, ensuring the following
precedence order:

1. Explicit overrides – CLI flags, Lambda event payloads, or `config/settings.yaml`.
2. Environment variables (including values from `.env`).
3. AWS Secrets Manager payloads resolved via `clients.secrets_manager.CredentialStore`.
4. Canonical defaults committed in `config/defaults.yml`.

The defaults file intentionally contains non-secret values and documents the
expected schema. Secrets are referenced by ARN under the `secrets` block and are
resolved into the configuration at load time. Each ARN maps specific keys from
the secret payload (for example `client_id`, `app_password`) into the final
configuration tree via dotted paths such as `jira.credentials.client_id`.

## Sections

### `aws`
Defines the default region used for AWS clients. The loader uses this value when
initialising the Secrets Manager client.

### `storage`
Contains DynamoDB and S3 configuration:

- `storage.dynamodb.jira_issue_table` – DynamoDB table backing the Jira cache.
- `storage.s3.bucket` / `storage.s3.prefix` – Artifact destinations for uploads.

### `jira`
Captures Jira connection details, including scopes used by the audit command and
placeholders for OAuth credentials. Secrets populate the `credentials` block at
runtime.

### `bitbucket`
Specifies the workspace, default repositories, and optional credential
placeholders.

### `webhooks`
Holds webhook metadata such as the shared secret used to validate incoming Jira
webhook calls.

### `secrets`
Lists AWS Secrets Manager ARNs and the schema for mapping secret payload fields
into the configuration tree. The loader merges secret payloads after reading the
defaults file but before applying environment variables and explicit overrides.

## Overrides

Create `config/settings.yaml` to capture environment-specific defaults without
modifying `defaults.yml`. The file uses the same schema and can be committed to
version control when it only contains non-secret values. Secrets should remain
in AWS Secrets Manager or environment variables.

## Validation

`load_config` performs schema validation to ensure mandatory keys (region, S3
bucket, Jira scopes, secret ARNs, etc.) are present. The application fails fast
with a descriptive error if any required values are missing, preventing partial
configuration from reaching runtime.

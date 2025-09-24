# CI/CD Workflow Notes

## Workflow overview
- **Workflow file**: `.github/workflows/ci.yml`
- **Triggers**:
  - Pushes to `main` and `feature/**`
  - Pull requests targeting `main`
  - Tags that match `v*.*.*`
  - Manual `workflow_dispatch` with inputs `run_uploader` (boolean) and `fix_version` (string)
- **Jobs**:
  - `python-checks` – always runs, installs dependencies, lints with `ruff check .` (soft fail), and executes `pytest -q`.
  - `package` – builds `dist/lambda_bundle.zip`, verifies the archive is non-empty, and uploads it for PRs and pushes (longer retention when run from a tag).
  - `cdk-synth` – creates a Python virtualenv, installs CDK dependencies, installs AWS CDK v2, and runs `cdk synth` from `infra/cdk`.
  - `optional-uploader` – runs only for manual `workflow_dispatch` events where `run_uploader` is `true`; conditionally configures AWS credentials via OIDC and invokes the ReleaseCopilot uploader CLI.

## OIDC setup
1. In AWS IAM, create (or update) a role that trusts your GitHub organisation/repository using the OpenID Connect provider `token.actions.githubusercontent.com`.
2. Attach the least-privilege permissions required to upload the Lambda bundle to your target S3 bucket.
3. Save the role ARN as the repository secret `AWS_ROLE_TO_ASSUME`.
4. Ensure the workflow has `permissions: { contents: read, id-token: write }` whenever OIDC is needed (already configured in `optional-uploader`).

## Required secrets and variables
- `AWS_ROLE_TO_ASSUME` (secret, optional) – enables the OIDC credential flow for the uploader job.
- `RC_S3_BUCKET` (secret) – destination bucket for manual uploads; when absent the uploader logs and exits gracefully.
- `AWS_REGION` (repository or organisation variable) – defaults to `us-west-2` when unset.

## Manual workflow runs
1. Open the **CI** workflow in the GitHub Actions tab and select **Run workflow**.
2. Choose the target branch/tag and optionally enable `run_uploader`.
3. Provide `fix_version` if you want to override the detected version (otherwise tag names or the current date are used).
4. When `run_uploader` is enabled, the workflow:
   - Ensures the Lambda bundle has been built by the `package` job.
   - Configures AWS credentials via OIDC when `AWS_ROLE_TO_ASSUME` is present.
   - Invokes `python -m releasecopilot.cli` with `--s3-prefix releasecopilot`, uploading into `s3://$RC_S3_BUCKET/releasecopilot/`.
   - Skips gracefully when the bucket secret is not provided.

## Local smoke tests
Run these commands before pushing to verify the core CI checks locally:
- `ruff check .`
- `pytest -q`
- `python scripts/package_lambda.py --out dist/lambda_bundle.zip` (or `bash scripts/package_lambda.sh` if the Python helper is unavailable)
- `cd infra/cdk && cdk synth`

## Guardrails
- Never place `secrets.*` references inside `if:` expressions. Read them into environment variables first and gate subsequent steps with `env.*`.
- Keep at least one job unconditional so pull requests and pushes always produce CI feedback.

## CI Quick Runbook
```bash
ruff check .
pytest -q
python scripts/package_lambda.py --out dist/lambda_bundle.zip
cd infra/cdk && cdk synth
```

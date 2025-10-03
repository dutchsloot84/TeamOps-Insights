# CDK CI Runbook

This runbook documents how the CDK GitHub Actions workflows operate and how to triage issues quickly. The workflows always run from the repository root so the top-level [`cdk.json`](../../cdk.json) with `"app": "python -m infra.cdk.app"` is automatically discovered.

## Workflow overview

1. **Checkout** the repository.
2. **Provision runtimes:** Node.js 20 (jsii requirement) and Python 3.11.
3. **Create a virtual environment** and install `infra/cdk/requirements.txt` (plus any root `requirements.txt` if needed).
4. **Install the AWS CDK CLI** globally (`npm install -g aws-cdk`).
5. **Diagnose** the working directory and confirm that `cdk.json` exists at the repository root.
6. **Run CDK commands** from the root: `npx cdk list`, `npx cdk synth`, and—once AWS credentials are configured via OIDC—`npx cdk diff` and `npx cdk deploy --require-approval never`.

## Minimal workflow snippet

```yaml
- uses: actions/checkout@v4

- uses: actions/setup-node@v4
  with:
    node-version: '20'

- uses: actions/setup-python@v5
  with:
    python-version: '3.11'

- name: Install CDK & Python deps
  run: |
    python -m venv .venv
    source .venv/bin/activate
    python -m pip install -U pip
    if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
    pip install -r infra/cdk/requirements.txt
    npm install -g aws-cdk

- name: Diagnose working dir & cdk.json
  run: |
    set -xeuo pipefail
    echo "PWD=$(pwd)"
    ls -la
    echo '--- cdk.json ---'
    test -f cdk.json && cat cdk.json || echo 'NO ROOT cdk.json FOUND'

- name: CDK List
  run: |
    source .venv/bin/activate
    npx cdk list

- name: CDK Synth
  run: |
    source .venv/bin/activate
    npx cdk synth

- name: Configure AWS credentials
  uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: ${{ secrets.DEPLOY_ROLE_ARN }}
    aws-region: us-west-2

- name: CDK Diff
  run: |
    source .venv/bin/activate
    npx cdk diff

- name: CDK Deploy
  run: |
    source .venv/bin/activate
    npx cdk deploy --require-approval never
```

## Common failures and fixes

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `--app is required either in command-line, in cdk.json or in ~/.cdk.json` | The workflow is not running from the repo root or `cdk.json` is missing/broken. | Ensure all steps execute from `${{ github.workspace }}` and the root `cdk.json` includes `"app": "python -m infra.cdk.app"`. |
| `ModuleNotFoundError: No module named 'aws_cdk'` | Virtual environment did not install `infra/cdk/requirements.txt`. | Confirm the install step runs *after* activating the venv and includes `pip install -r infra/cdk/requirements.txt`. |
| `ModuleNotFoundError: No module named 'core_stack'` (or similar) | Missing `infra/cdk/__init__.py` or relative imports. | Keep `infra/cdk/__init__.py` in place and use absolute imports like `from infra.cdk.core_stack import CoreStack`. |

Following this runbook keeps CI deterministic and mirrors the same commands developers run locally.

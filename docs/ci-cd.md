# ReleaseCopilot CI/CD

This document captures how the ReleaseCopilot infrastructure is validated and deployed with AWS CDK using GitHub Actions and OpenID Connect (OIDC).

## Overview

* The CDK application lives in `infra/cdk` and is executed through the portable wrapper `run_cdk_app.py`.
* GitHub Actions authenticates to AWS via the repository variable `OIDC_ROLE_ARN` and the `aws-actions/configure-aws-credentials` action.
* The workflow file `.github/workflows/cdk-ci.yml` runs validation on every pull request and performs full deploys on pushes to `main` and semantic tags.

## Local workflows

### Prerequisites

* Python 3.11 (or newer) with `pip`
* Node.js 18+ to run the AWS CDK CLI through `npx`

From the repository root you can run:

```bash
npm run cdk:list
npm run cdk:synth
npm run cdk:deploy:all
```

These commands run in the `infra/cdk` directory and invoke the wrapper so that `python` vs. `python3` differences do not matter.

If you need to troubleshoot interpreter mismatches, execute:

```bash
cd infra/cdk
python scripts/preflight.py
```

The preflight script prints the Python binary path, version, and operating system before re-executing `app.py`.

## GitHub Actions workflow

The `cdk-ci` workflow contains two jobs:

1. **validate** – installs dependencies, runs the preflight diagnostics, assumes the deploy role via OIDC, and executes `cdk list`, `cdk synth`, and `cdk diff`. The synthesized output is uploaded as a build artifact when available.
2. **deploy** – triggered on pushes to `main` or tags matching `v*`; it re-installs dependencies, assumes the same role, and runs `cdk deploy --require-approval never --all`.

Every job sets `permissions: id-token: write` and `contents: read`, and uses the repository variable `OIDC_ROLE_ARN` for the role to assume. The `Who am I` step runs `aws sts get-caller-identity` so you can confirm the workflow assumed the expected role.

## Troubleshooting

| Symptom | Suggested fix |
| --- | --- |
| `cdk list` prints usage information | Ensure you are running commands from the repository root through `npm run` (or directly within `infra/cdk`) so that `run_cdk_app.py` is used. |
| `Could not load credentials` in CI | Confirm the `OIDC_ROLE_ARN` repository variable is set and that the workflow still has `permissions: id-token: write`. |
| Access denied when uploading CDK assets | Verify the inline policy created from `infra/iam/policies/s3_bootstrap.json` (or generated via `scripts/compose_policies.py`) is attached to the deploy role. |

## Changelog

* 2024-05-18 – Removed the temporary diagnostic inventory job after validating least-privilege deploys. See the [successful deploy run](https://github.com/ReleaseCopilot/ReleaseCopilot-AI/actions/workflows/cdk-ci.yml?query=branch%3Amain+is%3Asuccess) for confirmation.

## Historian

* **Decisions** – Adopted OIDC for all CDK deploys and centralized on a single `cdk-ci` workflow.
* **Notes** – Diagnostic inventory output is no longer collected automatically; refer to the retained IAM policy templates for least-privilege updates.
* **Actions** – Continue to maintain the inline policies generated from `scripts/compose_policies.py` and adjust permissions as new infrastructure components are introduced.

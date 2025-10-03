# CDK Workflow Preflight Checklist

The `cdk-ci` GitHub Actions workflow performs a lightweight preflight before
running `cdk list`, `cdk synth`, or other AWS CDK commands. The checks confirm
the repository uses a single root-level `cdk.json` and that the configured
entry point exists before invoking the CDK CLI.

## What the preflight checks

1. **Repository layout** – `scripts/ci/verify_cdk_root_layout.sh` ensures
   `cdk.json` lives at the repository root, extracts the `app` command, and
   verifies that the referenced entry file exists. The guard also blocks nested
   `infra/cdk/infra/cdk` directories that previously caused confusion.
2. **Language dependencies** – The workflow installs Python requirements from
   `requirements.txt` (when present) and `infra/cdk/requirements.txt` before
   running the CDK CLI from the repository root.
3. **CLI execution** – With the layout verified, the workflow runs `npx cdk
   list`, `npx cdk synth`, and, when credentials are available, `npx cdk diff`
   and `npx cdk deploy --require-approval never`.

## Local debugging tips

Run the same checks locally from the repository root:

```bash
./scripts/ci/verify_cdk_root_layout.sh
python -m venv .venv && source .venv/bin/activate
python -m pip install -r infra/cdk/requirements.txt
npx cdk list
```

If the `cdk list` command fails locally, execute the `app` command printed by
the verification script (for example `python infra/cdk/app.py`) to inspect the
underlying stack trace before retrying the CDK CLI.

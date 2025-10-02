# CDK Infrastructure

The GitHub Actions workflows expect the canonical CDK application configuration to live at `infra/cdk/cdk.json`. Any other `cdk.json` files (for example legacy copies under `cdk/`) are deprecated and ignored by CI, and a lint check will fail the pipeline if they are committed. Update or remove any duplicates to keep the infra pipeline healthy.

Preflight validation in CI will normalize the `app` command to use `python3`, ensure the referenced entrypoint (for example `infra/cdk/run_cdk_app.py`) exists and is executable, and fall back to invoking CDK with `-a "$APP"` if automatic detection fails. Keep `cdk.json` and the entry script in sync to avoid deployment failures.

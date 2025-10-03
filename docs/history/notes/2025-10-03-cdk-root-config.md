# CDK root configuration markers

- **Decision:** Adopt root-level `cdk.json` with the `python -m infra.cdk.app` module entry so CDK always resolves the app from the repository root.
- **Note:** GitHub Actions workflows removed every `cd infra/cdk` hop; all `npx cdk` commands execute in the root context.
- **Action:** Enforce dependency installation via `infra/cdk/requirements.txt`, keep absolute imports, and ensure `infra/cdk/__init__.py` exists.
- **Action:** Add a diagnostic step (printing `$PWD` and `cdk.json`) and optionally use `-a "python -m infra.cdk.app"` during the migration period.

# CDK Change Checklist

Use this checklist before opening a pull request that touches the infrastructure code.

- [ ] Root `cdk.json` exists with `"app": "python -m infra.cdk.app"`.
- [ ] No `infra/cdk/cdk.json`; no `infra/cdk/infra/cdk/` duplicate directory.
- [ ] `infra/cdk/__init__.py` exists and application imports are absolute (e.g. `from infra.cdk.core_stack import ...`).
- [ ] `infra/cdk/requirements.txt` includes `aws-cdk-lib`, `constructs`, and `boto3`.
- [ ] Local validation from the repository root succeeds: `npx cdk list` and `npx cdk synth`.
- [ ] GitHub Actions workflows and scripts do **not** `cd infra/cdk` or override the app with ad-hoc `-a` flags.

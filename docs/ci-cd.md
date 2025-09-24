# CI/CD Workflow Notes

- GitHub Actions expressions in this repository must be wrapped with the `${{ ... }}` syntax to ensure they are parsed correctly.
- Secrets such as `AWS_OIDC_ROLE_ARN` are evaluated with step-level `if` guards so that jobs continue running even when secrets are not configured.

### Guardrails: secrets in workflow conditionals

- **Wrap expressions**: Any use of `secrets.*` must be inside `${{ ... }}`.
  - ✅ `if: ${{ secrets.AWS_OIDC_ROLE_ARN != '' }}`
  - ❌ `if: secrets.AWS_OIDC_ROLE_ARN != ''`
- **Prefer step-level gating** over job-level:
  - Keep at least one job always created so PRs/pushes show checks.
  - Gate AWS-specific steps with `if:` instead of gating the entire job.
- **OIDC requirements**:
  - Add `permissions: id-token: write` at the job level.
  - Use `aws-actions/configure-aws-credentials@v4` only when the role secret is present.

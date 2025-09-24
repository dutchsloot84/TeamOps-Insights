# CI/CD Workflow Notes

- GitHub Actions expressions in this repository must be wrapped with the `${{ ... }}` syntax to ensure they are parsed correctly.
- Secrets such as `AWS_OIDC_ROLE_ARN` are evaluated with step-level `if` guards so that jobs continue running even when secrets are not configured.

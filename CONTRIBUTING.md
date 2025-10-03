# Contributing

Thank you for investing in Release Copilot! This guide captures contributor expectations that do not fit elsewhere in the docs set.

## Notes & decision markers

Release Copilot ingests structured markers from issues and pull requests (Decision, Note, Action, Blocker) when building the weekly history snapshots. To keep the noise level low and make PR review threads easy to scan, prefer **block style markers** when you have multiple follow-up items to record:

```markdown
Decision:
- Canonicalize CDK config to infra/cdk/cdk.json.
- Treat any additional cdk.json outside infra/cdk/cdk.json as unsupported for CI.

Action:
- Add guardrail script to fail the build if non-canonical cdk.json files are committed.
```

Block style keeps every bullet tied to a single marker heading so reviewers do not have to parse repeated prefixes, while Git Historian still captures each bullet individually.

Inline markers are still supported and are handy for short, one-off notes:

```markdown
Note: Retry `cdk list` with `--verbose` if the default invocation flakes.
```

> **Tip:** Inline style is great for scratch notes or quick comments, but block style is the preferred format for PR reviews, RFC feedback, and any thread where you are communicating multiple decisions or follow-up items.


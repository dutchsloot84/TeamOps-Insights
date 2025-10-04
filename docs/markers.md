# Marker conventions

Release Copilot recognizes four structured markers in GitHub issues and pull requests: **Decision**, **Note**, **Action**, and **Blocker**. The Git Historian job ingests these markers and mirrors them into weekly history snapshots so the team can scan highlights without trawling through every thread.

## Preferred: block style for PR reviews

Use a marker heading followed by one or more bullet points when recording multiple outcomes in a review comment. Each bullet is captured as a separate entry while staying visually compact for humans:

```markdown
Decision:
- Canonicalize CDK config to infra/cdk/cdk.json and normalize the app to python3 in CI.
- Treat any additional cdk.json outside infra/cdk/cdk.json as unsupported for CI.

Action:
- Add guardrail script to fail the build if non-canonical cdk.json files are committed.
- Document canonical location and preflight expectations for infra contributors.
```

Multi-line bullets are supported — indent the continuation lines to keep them attached to the bullet.

## Inline style for quick notes

Inline markers remain available for short call-outs, TODOs, or fast triage notes:

```markdown
Note: CI installs `jq` up front before calling the CDK entry point.
Blocker: Builds fail until duplicate `cdk.json` files are removed.
```

The collector continues to index these comments, but inline style can feel noisy when you have to repeat the marker on every line.

## Mixing styles

It is fine to mix styles in the same comment. For example, you might open with a `Decision:` block and close with an inline `Action:` reminder. The parser will stop each block when it reaches another marker or a blank line, so keep related bullets grouped together.

## Configuration reference

The default marker list lives in `config/defaults.yml` under `historian.sources.notes.comment_markers`. Update that list if your team adds new marker types.


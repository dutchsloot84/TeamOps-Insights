# Notes & Decisions — #226 Simplify CDK workflow to use root cdk.json

_Repo:_ dutchsloot84/ReleaseCopilot-AI
_Source:_ https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/226

- Decision (Uncategorized) — 2025-10-03 by @dutchsloot84
  Standardize on a single root-level cdk.json with "app": "python -m infra.cdk.app", and require all CDK commands (local + CI) to run from the repo root.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/226#issuecomment-3367012691) <!-- digest:c053626c9ce4e6c5747594e410e37813691df8317d5ed401565ce8c029feabf2 -->

- Note (Uncategorized) — 2025-10-03 by @dutchsloot84
  Previous failures (--app is required…) were caused by workflows cd infra/cdk and duplicate/nested cdk.json. This PR removes those patterns and aligns with AWS CDK best practices.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/226#issuecomment-3367012691) <!-- digest:b2f6e9dec2dc2a410a8064c35d64a47a830d1a62f3eefaf0ccb036e0487380ff -->

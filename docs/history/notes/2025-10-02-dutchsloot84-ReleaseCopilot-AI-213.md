# Notes & Decisions — #213 Improve CDK CI preflight diagnostics

_Repo:_ dutchsloot84/ReleaseCopilot-AI
_Source:_ https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/213

- Decision (Uncategorized) — 2025-10-02 by @dutchsloot84
  CDK CI workflow now includes explicit workspace diagnostics, cdk.json validation, dependency installs (Node/Python), and a preflight step with cdk doctor before running cdk list.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/213#issuecomment-3362676731) <!-- digest:7adee1c2e1be0b33c45c29485c86e8b55dfe8321ce73e2835a224e8d380a3551 -->

- Note (Uncategorized) — 2025-10-02 by @dutchsloot84
  If cdk list fails in CI, the workflow now retries with verbose logging and explicit -a app fallback to surface actionable errors.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/213#issuecomment-3362676731) <!-- digest:8bb7034f92729c555441a091c69caf61a166fe0d5b59e89a87d6b9d266b244ec -->

- Action (Uncategorized) — 2025-10-02 by @dutchsloot84
  Documented the preflight process in CI/CD docs and added a changelog entry to guide future contributors.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/213#issuecomment-3362676731) <!-- digest:002945a8443ce97f7284ad7a94e4f219cd7bb293515c76b29a8bd4ec3ee734eb -->

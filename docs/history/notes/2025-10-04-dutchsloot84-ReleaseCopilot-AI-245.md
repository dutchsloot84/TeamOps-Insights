# Notes & Decisions — #245 Add reconciliation DLQ alarm and runbook guidance

_Repo:_ dutchsloot84/ReleaseCopilot-AI
_Source:_ https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/245

- Decision (Uncategorized) — 2025-10-04 by @dutchsloot84
  Create a CloudWatch alarm on the reconciliation DLQ `ApproximateNumberOfMessagesVisible` with a tunable threshold (default ≥1).
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/245#issuecomment-3368489773) <!-- digest:4082b6ced453d01768bf3c6c6a08e5b734da8979bbc15fd5cf1610de669eee37 -->

- Decision (Uncategorized) — 2025-10-04 by @dutchsloot84
  Support optional SNS notifications for the DLQ alarm when `alarmEmail` or `snsTopicArn` is provided.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/245#issuecomment-3368489773) <!-- digest:8084584448e90448b9c60d11024b80c194fe3eb048c3ea102f5756d665cfee71 -->

- Decision (Uncategorized) — 2025-10-04 by @dutchsloot84
  Publish the reconciliation DLQ ARN and URL as stack outputs to aid discovery and automation.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/245#issuecomment-3368489773) <!-- digest:740c62b853d858084c3e2786ad2f7475071d5c3127ca2b5c420bd4dda02011e1 -->

- Action (Uncategorized) — 2025-10-04 by @dutchsloot84
  Implement the alarm and outputs in infra/cdk/core_stack.py and add a shared SNS alarm action helper.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/245#issuecomment-3368489773) <!-- digest:ff51403a6bbd543b18da38e1bb61f9aaed53023ca8a15c7a087763a84791500d -->

- Action (Uncategorized) — 2025-10-04 by @dutchsloot84
  Extend tests in tests/infra/test_core_stack.py to assert the DLQ alarm and the new stack outputs.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/245#issuecomment-3368489773) <!-- digest:132dc9663f5e83f428ddb6eac180fae92a4326d6208de5a280db4bc3c56a3916 -->

- Action (Uncategorized) — 2025-10-04 by @dutchsloot84
  Update docs/runbooks/health_smoke.md with DLQ triage and replay steps; link readiness verification.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/245#issuecomment-3368489773) <!-- digest:709459ea68965d4ae30fc8cf14818782ac4e273039379e9467ebf0f580c8ea51 -->

- Note (Uncategorized) — 2025-10-04 by @dutchsloot84
  Thresholds and evaluation periods are configurable via CDK context; start conservative to avoid noise and tune with ops feedback.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/245#issuecomment-3368489773) <!-- digest:41ab5a94a77c70a8ed4314509ff8d538c6c66aa85bd88f9c7c2a5ddfa06f625a -->

- Note (Uncategorized) — 2025-10-04 by @dutchsloot84
  Operators can verify via `npx cdk synth -a "python -m infra.cdk.app"` and `pytest tests/infra/test_core_stack.py -q`.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/245#issuecomment-3368489773) <!-- digest:7f6ce53cd8789d7b7439e1cbce3837c9eaa7f3b41301991163a424c939b3176a -->

- Blocker (Uncategorized) — 2025-10-04 by @dutchsloot84
  None identified post-implementation; monitor for false-positive alarms after first week and adjust thresholds as needed.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/245#issuecomment-3368489773) <!-- digest:5349ac008948916ab433da316865e2fc7e7ce8c2d59ace1da25b7eddbf566da7 -->

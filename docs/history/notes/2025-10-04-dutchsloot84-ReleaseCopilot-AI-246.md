# Notes & Decisions — #246 feat: add composite jira cache keys with idempotency

_Repo:_ dutchsloot84/ReleaseCopilot-AI
_Source:_ https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/246

- Decision (Uncategorized) — 2025-10-04 by @dutchsloot84
  Use DynamoDB composite key (PK=issue_key, SK=updated_at), enable PITR, and export table name/ARN for least-privilege IAM.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/246#issuecomment-3368513336) <!-- digest:236838130075ee3604de22b26ffd5659825199dba7ef461db8aebc06c99d0245 -->

- Decision (Uncategorized) — 2025-10-04 by @dutchsloot84
  Persist webhook deliveries with composite key + idempotency_key; tombstone deletes on newest sort key; reconciliation skips stale and flags missing as deletes.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/246#issuecomment-3368513336) <!-- digest:f89ed386163e876bd087009eac4ec7035d242573075c4d11754433ae74fb7cb4 -->

- Decision (Uncategorized) — 2025-10-04 by @dutchsloot84
  Health checks must validate HASH+RANGE via sentinel write/delete round-trip.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/246#issuecomment-3368513336) <!-- digest:29641d9bd22cfba8c0ec7341d6f7d58932fa72aa7ca8c248c54ecfc190a0a6a0 -->

- Action (Uncategorized) — 2025-10-04 by @dutchsloot84
  Update infra/cdk/core_stack.py to (re)create JiraIssuesTable with PK/SK, PITR on, and stack outputs; verify with `npx cdk synth -a "python -m infra.cdk.app"`.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/246#issuecomment-3368513336) <!-- digest:54c98d1baba0299b8c45c406e193108dbbbff51fae32c2ef7da890cb52b31b9a -->

- Action (Uncategorized) — 2025-10-04 by @dutchsloot84
  Change services/jira_sync_webhook/handler.py and services/jira_reconciliation_job/handler.py for idempotent upserts/tombstones; adjust clients/jira_store.py for reverse index scan + filtering.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/246#issuecomment-3368513336) <!-- digest:2af184fd4075fef33fba7a74e6464057f164a16fdf853829aca897e894f988bf -->

- Action (Uncategorized) — 2025-10-04 by @dutchsloot84
  Update src/config/loader.py and src/ops/health.py to resolve table and round-trip composite sentinels.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/246#issuecomment-3368513336) <!-- digest:1877ead62af2c47dc0bece143eade8e6218068319d574030db70efc195e555aa -->

- Action (Uncategorized) — 2025-10-04 by @dutchsloot84
  Add tests in tests/services/*_idempotency.py, tests/ops/test_health_checks.py, and tests/test_core_infra_stack.py; run `pytest -q`.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/246#issuecomment-3368513336) <!-- digest:80f680a39516aacb7808d7ad70c99a1e8966b1f5955b6f4211dd7ab51f74ae7d -->

- Action (Uncategorized) — 2025-10-04 by @dutchsloot84
  Document schema/ops in docs/deployment.md#dynamodb-schema-notes and docs/runbooks/health_smoke.md#invocation; index in docs/adr/README.md.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/246#issuecomment-3368513336) <!-- digest:690bd824821e3125302d9ca88f109309492ca445d10ed99d5af977685b6902ab -->

- Note (Uncategorized) — 2025-10-04 by @dutchsloot84
  Operators should prune stale sort keys during verification; see docs/observability.md#jira-cache-idempotency.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/246#issuecomment-3368513336) <!-- digest:02456627a8139c9df6ac1b7a84eb3909f9294af01277b6547005c3d9a05f2b5e -->

- Note (Uncategorized) — 2025-10-04 by @dutchsloot84
  Stack outputs (table name/ARN) enable precise IAM scoping for Lambda roles.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/246#issuecomment-3368513336) <!-- digest:1fb12fba14c30663bfa0647bd1a0686318c447e466b61247bff930d8d82bbb1c -->

- Blocker (Uncategorized) — 2025-10-04 by @dutchsloot84
  Plan & execute migration/backfill from legacy table; add a runbook step for stale sort-key pruning.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/246#issuecomment-3368513336) <!-- digest:27c6aa286418a119f0c4b12ffb11c7f3444b8bd1671a813cd6f7066d9769b99f -->

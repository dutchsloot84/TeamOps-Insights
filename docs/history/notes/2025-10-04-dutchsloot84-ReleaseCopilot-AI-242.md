# Notes & Decisions — #242 Tighten core stack log policies and integrate cdk-nag

_Repo:_ dutchsloot84/ReleaseCopilot-AI
_Source:_ https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/242

- Decision (Uncategorized) — 2025-10-04 by @dutchsloot84
  Scope Lambda logging permissions to **function-specific CloudWatch Log Groups**; no wildcard resources.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/242#issuecomment-3368488004) <!-- digest:ef10e2e31ed029659c3aa5042cd6144a1970fcf90b4f5343a0e9410c47a8394c -->

- Decision (Uncategorized) — 2025-10-04 by @dutchsloot84
  Enforce **TLS/SecureTransport** on the artifacts S3 bucket and enable **API Gateway access logging** to reduce IAM blast radius.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/242#issuecomment-3368488004) <!-- digest:7a3abccd7df8820abea45b5e84e3b4f359380a299ead5641af444281c9df30d8 -->

- Decision (Uncategorized) — 2025-10-04 by @dutchsloot84
  Enable **cdk-nag** (AwsSolutions checks) during synth with documented suppressions in code.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/242#issuecomment-3368488004) <!-- digest:f6435004ff1e32df8f424692b5b69a219e2be4e1c53e20c352591130e2921e76 -->

- Decision (Uncategorized) — 2025-10-04 by @dutchsloot84
  Deprecate legacy CDK entry `cdk/stacks/core_stack.py` in favor of `infra/cdk/app.py`.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/242#issuecomment-3368488004) <!-- digest:956f6db755e4a973a66e45e740c3c79064ca253ab93d08f059a01b8f6ce66647 -->

- Action (Uncategorized) — 2025-10-04 by @dutchsloot84
  Update `infra/cdk/core_stack.py` to replace `/aws/lambda/*` with explicit ARNs:
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/242#issuecomment-3368488004) <!-- digest:bff2f0cb0292531e0fd324c42169e9e44bcd37901a75a7c79d629e3c4d4c2a63 -->

- Action (Uncategorized) — 2025-10-04 by @dutchsloot84
  Example: `arn:aws:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/lambda/ReleaseCopilot-*:*`
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/242#issuecomment-3368488004) <!-- digest:a1b7f106c0146382e6e058e2ca75defa611e95c6f0778b52a1a2283c3c101d30 -->

- Action (Uncategorized) — 2025-10-04 by @dutchsloot84
  Bind each function’s `LogGroup` construct and grant only `logs:CreateLogStream`, `logs:PutLogEvents`.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/242#issuecomment-3368488004) <!-- digest:0a54385f09610102611bd14f381b6f14e22c5fefac75c2a5adcf4cd14b0c7409 -->

- Action (Uncategorized) — 2025-10-04 by @dutchsloot84
  Wire **cdk-nag** in `infra/cdk/app.py` (Aspects + AwsSolutionsChecks) and add suppressions via `NagSuppressions` where required.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/242#issuecomment-3368488004) <!-- digest:ac1da7158f716dff04c9bacebea044ca7427b682581fbd94dcba1f7c639dd466 -->

- Action (Uncategorized) — 2025-10-04 by @dutchsloot84
  Add `aws:SecureTransport` bucket policy condition on the artifacts bucket; enable **API GW stage** `accessLogSettings` to a dedicated log group.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/242#issuecomment-3368488004) <!-- digest:0f11a0f84565476b2875e4cfeb2212763eadb346d92babb603bfc2ca40d20927 -->

- Action (Uncategorized) — 2025-10-04 by @dutchsloot84
  Refresh tests in `tests/infra/test_core_stack.py`:
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/242#issuecomment-3368488004) <!-- digest:7edca87a4839ed53acb335e9a411e5d867b4d0d9a59d4aed23a11b74ed7aa268 -->

- Action (Uncategorized) — 2025-10-04 by @dutchsloot84
  `test_log_group_policy_is_scoped` asserts no `Resource:"*"` and matches explicit LogGroup ARNs.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/242#issuecomment-3368488004) <!-- digest:0edcb9a4885c625ba0b0565ca5ba34510014d709a6987b1e4cbe05ab85ddca12 -->

- Action (Uncategorized) — 2025-10-04 by @dutchsloot84
  `test_cdk_nag_passes_or_has_documented_suppressions` captures the nag baseline.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/242#issuecomment-3368488004) <!-- digest:eb04689a3a44237e8db75dda275dc830eee4eacbe25e480f8ff6507a68421560 -->

- Action (Uncategorized) — 2025-10-04 by @dutchsloot84
  Mark `cdk/stacks/core_stack.py` as **deprecated** in `README.md` and `docs/deployment.md`.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/242#issuecomment-3368488004) <!-- digest:fe9bd9a4fabe03cbd02796d8d032aefff194ddd91dc8ec84a485c60179059f8d -->

- Note (Uncategorized) — 2025-10-04 by @dutchsloot84
  Validation commands:
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/242#issuecomment-3368488004) <!-- digest:cc48204040d953e95eac5b38b8862a61dcc8d4556a862ad270ca5a099200a98c -->

- Note (Uncategorized) — 2025-10-04 by @dutchsloot84
  `pytest tests/infra/test_core_stack.py -q`
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/242#issuecomment-3368488004) <!-- digest:6a108317268194528c5457efcc8348071e1c55228116984415188341908033b0 -->

- Note (Uncategorized) — 2025-10-04 by @dutchsloot84
  `npx cdk synth -a "python -m infra.cdk.app"`
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/242#issuecomment-3368488004) <!-- digest:75284fa61cdd604ef154458c40394818000b9646c36a25898a2516d2e32caa31 -->

- Note (Uncategorized) — 2025-10-04 by @dutchsloot84
  Observability: API Gateway access logs now flow to `LogGroup: ApiGatewayAccessLogs` (CDK-provisioned).
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/242#issuecomment-3368488004) <!-- digest:f60181fc48b7fbf901965c3ee8296e45a322b6b6c89c10afe0d319dbde78cab4 -->

- Note (Uncategorized) — 2025-10-04 by @dutchsloot84
  Least-privilege doc updated: `docs/ci-cd-least-priv.md#policy-artifacts`.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/242#issuecomment-3368488004) <!-- digest:8d043abdd197bf527bdb057d216df57dfae271de1619657aaaf996bd9634112d -->

- Blocker (Uncategorized) — 2025-10-04 by @dutchsloot84
  None currently. Monitor future cdk-nag findings when adding new Lambdas.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/242#issuecomment-3368488004) <!-- digest:bc13889609492b34b5baf218defeb3cac3c2971dd452de01ebf541d885f8e3fa -->

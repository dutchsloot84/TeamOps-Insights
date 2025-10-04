# Notes & Decisions — #243 Ensure Lambda handlers use shared logging

_Repo:_ dutchsloot84/ReleaseCopilot-AI
_Source:_ https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/243

- Decision (Uncategorized) — 2025-10-04 by @dutchsloot84
  Initialize a shared JSON logger in all Jira Lambda handlers and standardize on `get_logger(__name__)` via `releasecopilot.logging_config` to enforce redaction.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/243#issuecomment-3368491258) <!-- digest:c51f520a343e01862f7851b8eb642b2537097c0915647fc2009758e0f0f6f2dd -->

- Decision (Uncategorized) — 2025-10-04 by @dutchsloot84
  Treat redaction of sensitive fields (e.g., password, token, secret, bearer, oauth) as a required logging invariant for Lambda execution paths.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/243#issuecomment-3368491258) <!-- digest:ffb92d04e3a0298e18c33fa5e4230f18090e1a1553c2cf4a89a86a0f17c66087 -->

- Action (Uncategorized) — 2025-10-04 by @dutchsloot84
  Update `services/jira_sync_webhook/handler.py` to call `configure_logging()` at import (idempotent) and replace `logging.getLogger()` with `get_logger(__name__)`.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/243#issuecomment-3368491258) <!-- digest:a5aacb9100b12115381ae4d827dea2c12d07ca64ed40d7265838d95ef065d611 -->

- Action (Uncategorized) — 2025-10-04 by @dutchsloot84
  Update `services/jira_reconciliation_job/handler.py` to initialize shared logging at import and use `get_logger(__name__)` for all emits.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/243#issuecomment-3368491258) <!-- digest:697ee34b8c6577318d8568f056ca739776f037f55c71e1d00936b2270a137a93 -->

- Action (Uncategorized) — 2025-10-04 by @dutchsloot84
  Update `services/ingest/jira_ingestor/handler.py` to initialize shared logging at import and use `get_logger(__name__)` for all emits.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/243#issuecomment-3368491258) <!-- digest:e3d29c5812bfd93d352e75e0a74c340730e0ec5ad3cd96a21601c845693c0288 -->

- Action (Uncategorized) — 2025-10-04 by @dutchsloot84
  Add regression tests `tests/services/test_jira_webhook_logging_redaction.py`, `tests/services/test_reconciliation_logging_redaction.py`, and `tests/services/test_ingestor_logging_redaction.py` that enable JSON logging and assert sensitive fields are redacted when passed via `extra`.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/243#issuecomment-3368491258) <!-- digest:1f538d9f519cac99333bd11f406cf400ea64c4ce19ee195bacfc2a9d4d6d0c70 -->

- Action (Uncategorized) — 2025-10-04 by @dutchsloot84
  Document Lambda logger reuse and redaction guarantees in `docs/observability.md#lambda-redaction`.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/243#issuecomment-3368491258) <!-- digest:f7072dde2b52e6366127f74290e767ba12a07ccd18265d16a5c4ec6a49ab59ff -->

- Note (Uncategorized) — 2025-10-04 by @dutchsloot84
  Verify locally with `pytest tests/services -q`; warm-start safety ensured by idempotent `configure_logging()` in each handler module.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/243#issuecomment-3368491258) <!-- digest:dec926f1d3a8bb14c4bf3b7e5165f38c5a3bea9ec765a64b186e85255eb8f225 -->

- Note (Uncategorized) — 2025-10-04 by @dutchsloot84
  Handlers now inherit the same log structure/filters as the CLI, reducing drift between local and Lambda executions.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/243#issuecomment-3368491258) <!-- digest:2f155d8dedb2f70d5fcb1863dbdd1a2805e16572d9220b5792dc8a410c8d1e9a -->

- Blocker (Uncategorized) — 2025-10-04 by @dutchsloot84
  None identified; monitor for double-initialization warnings in CloudWatch and adjust guard if needed.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/243#issuecomment-3368491258) <!-- digest:ce3bd345f36a191ed62eac36f40566f450eef581b14de520273cf727d1079087 -->

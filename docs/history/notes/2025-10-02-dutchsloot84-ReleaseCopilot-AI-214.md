# Notes & Decisions — #214 Fix CDK CI canonicalization and python3 preflights

_Repo:_ dutchsloot84/ReleaseCopilot-AI
_Source:_ https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/214

- Decision (Uncategorized) — 2025-10-02 by @dutchsloot84
  Canonicalize CDK config to cdk.json and normalize the app to use python3 in CI.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/214#issuecomment-3362858117) <!-- digest:f9e68dcf9018b4f43f2aef352f7779272e338dc89b0dbced2c409fc662b357f4 -->

- Decision (Uncategorized) — 2025-10-02 by @dutchsloot84
  Treat any additional cdk.json outside cdk.json as unsupported for CI.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/214#issuecomment-3362858117) <!-- digest:5878ada0061dee81351587a201e4a5735359c0d55734b52c00abef0d93770a16 -->

- Note (Uncategorized) — 2025-10-02 by @dutchsloot84
  CI now installs jq up front, verifies the entrypoint exists, and runs cdk doctor before listing.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/214#issuecomment-3362858117) <!-- digest:7d375e263a2720a52cb7385476141c61c87ae9710ca9e2adb46a6d7349cc9fe1 -->

- Note (Uncategorized) — 2025-10-02 by @dutchsloot84
  cdk list is retried with verbose logs and an explicit -a "$APP" fallback for clearer failures.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/214#issuecomment-3362858117) <!-- digest:0cee311b19c5ce18fcede1a7f017efdf2b31576045183af5ba83a752dd67bb7e -->

- Action (Uncategorized) — 2025-10-02 by @dutchsloot84
  Add guardrail script to fail the build if non-canonical cdk.json files are committed.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/214#issuecomment-3362858117) <!-- digest:439961e8ce1aceccf7c2cdfc092a4131f4e7942d208deab6df3f00f7cc1a6c26 -->

- Action (Uncategorized) — 2025-10-02 by @dutchsloot84
  Document canonical location and preflight expectations for infra contributors.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/214#issuecomment-3362858117) <!-- digest:7d4d8b05e85eb511b6af18ecafc5d2274a75f3c0da98fdc48e82d67069c251aa -->

- Action (Uncategorized) — 2025-10-02 by @dutchsloot84
  Remove or migrate any legacy cdk.json files to cdk.json.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/214#issuecomment-3362858117) <!-- digest:fb4408988a375b49c36f6782fcafc9a8851ce33533f87fef8dc8479f55752241 -->

- Blocker (Uncategorized) — 2025-10-02 by @dutchsloot84
  Builds will fail until all extra cdk.json files are removed or aligned with the canonical path.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/214#issuecomment-3362858117) <!-- digest:04f06864da93d788a65626ee077438ce95d736e4c6afc14d6f094575ea97f09f -->

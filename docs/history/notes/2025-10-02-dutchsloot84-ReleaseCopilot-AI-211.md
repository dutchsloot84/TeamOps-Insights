# Notes & Decisions — #211 feat: harden CDK deploy pipeline

_Repo:_ dutchsloot84/ReleaseCopilot-AI
_Source:_ https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/211

- Decision (Uncategorized) — 2025-10-02 by @dutchsloot84
  Use GitHub OIDC for CI/CD (no static keys); add portable CDK runner + npm scripts for cross-platform use.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/211#issuecomment-3358565856) <!-- digest:64f6206a6c2fa09b4c79638672a6e38ac9fa98a66001d58530f9c905ca82adf0 -->

- Decision (Uncategorized) — 2025-10-02 by @dutchsloot84
  Pipeline enforces preflight → synth/diff → gated deploy.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/211#issuecomment-3358565856) <!-- digest:03015bb4d896d67e5ed88e6705bf1b8a8fdfc5511ec36da25573c1b02df2a91c -->

- Decision (Uncategorized) — 2025-10-02 by @dutchsloot84
  Replace temp diagnostic job with least-privilege policy templates + composer script.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/211#issuecomment-3358565856) <!-- digest:227b8655565af7b37ae702be84bee234599f6a5d2fd648fa2986db11a807251f -->

- Note (Uncategorized) — 2025-10-02 by @dutchsloot84
  Preflight reduces failed deploys; docs/changelog updated with IAM hardening guidance.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/211#issuecomment-3358565856) <!-- digest:62114cb784ef0786a69838798e1f97379717a6fdd362a66d59429c889c3aaa82 -->

- Action (Uncategorized) — 2025-10-02 by @dutchsloot84
  Infra to attach generated inline policies + detach temp managed ones.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/211#issuecomment-3358565856) <!-- digest:afce42535d0d18e9d3090dc620fd31dec2ff5822864b9f8fa324262be2b7f163 -->

- Action (Uncategorized) — 2025-10-02 by @dutchsloot84
  Archive cdk diff outputs on next tag for traceability.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/211#issuecomment-3358565856) <!-- digest:f021f0e0f13b434509964cf6cf68c3f6240475b132032aa26dcd30e918e3b3d5 -->

- Action (Uncategorized) — 2025-10-02 by @dutchsloot84
  Record ADR for CI identity + least-priv model.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/211#issuecomment-3358565856) <!-- digest:ab1f04bd1ae37b31be218d68b7d6ddf3e85e5926011b069fc2e28b39127c5828 -->

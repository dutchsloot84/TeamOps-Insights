# Notes & Decisions — #230

_Repo:_ dutchsloot84/ReleaseCopilot-AI
_Source:_ https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/230#issuecomment-3367485823

- Decision (Uncategorized) — 2025-10-03 by @dutchsloot84
  Adopt **block-style markers** as the preferred format across Issues/PRs to reduce noise and improve multi-line parsing.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/230#issuecomment-3367485823) <!-- digest:443712c4b6561bc020ea5b5344932f023ce46db72ad869122c7616e0a5201446 -->

- Decision (Uncategorized) — 2025-10-03 by @dutchsloot84
  Keep **backwards compatibility**: inline single-line markers remain valid; the collector parses both.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/230#issuecomment-3367485823) <!-- digest:7c599ab08d36648aa6ac34f2b951eb8f83b8ba38845ffd0a1a8530d12a31671a -->

- Decision (Uncategorized) — 2025-10-03 by @dutchsloot84
  Normalize output to **indented, multi-line bullets** in mirrored notes to preserve human readability.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/230#issuecomment-3367485823) <!-- digest:e7bd7a5d5d60eb9bc175be3dbc741d0ba611f612fd379066c1d6bdc0564867a3 -->

- Note (Uncategorized) — 2025-10-03 by @dutchsloot84
  Parser handles nested bullets and wrapped lines; leading `- ` or `* ` are supported.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/230#issuecomment-3367485823) <!-- digest:76707a85f0b4d86430b26267b19b2ab85ef2596b0835acfe092b5a5d79337256 -->

- Note (Uncategorized) — 2025-10-03 by @dutchsloot84
  Deduping is by (type, text, source URL, date); identical entries won’t be mirrored twice.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/230#issuecomment-3367485823) <!-- digest:cdf14cfb69ceb9af4a13bfb976fb365e57d2b990b73dfafae45092b5f3041211 -->

- Note (Uncategorized) — 2025-10-03 by @dutchsloot84
  Performance: parsing added ~O(n) per comment; negligible at current repo scale.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/230#issuecomment-3367485823) <!-- digest:da9ad5ff32b2b14ef93195d5c2a0a8394c06233b7b86a7f367946f82b0ce29a0 -->

- Action (Uncategorized) — 2025-10-03 by @dutchsloot84
  (Owner: Shayne) Add the **Marker Guide** link to the PR/Issue templates’ help text by **EOW**.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/230#issuecomment-3367485823) <!-- digest:6e5ae4924a7fd812f99e01bfe57991943195acd06312666f540303528ed9f3e2 -->

- Action (Uncategorized) — 2025-10-03 by @dutchsloot84
  (Owner: Shayne) Run the Historian job manually on `main` to verify end-to-end mirroring **today**.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/230#issuecomment-3367485823) <!-- digest:1b1b21ba99632ee9f7daac0e757a2c90e34149c69ed3c8f3b2ce31ce04404c70 -->

- Action (Uncategorized) — 2025-10-03 by @dutchsloot84
  (Owner: Shayne) Post a one-time FYI in the **Contributing** doc introducing the new block style **today**.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/230#issuecomment-3367485823) <!-- digest:8977d04852e727de9e241456a46b00c663a532b7f70c69c7f54a5fcb7a453c35 -->

# Notes & Decisions — #215 Standardize Markers with Block Style

_Repo:_ dutchsloot84/ReleaseCopilot-AI
_Source:_ https://github.com/dutchsloot84/ReleaseCopilot-AI/issues/215

- Decision (Completed) — 2025-10-03 by @dutchsloot84
  Adopt **block-style markers** as the preferred format across Issues/PRs to reduce noise and improve multi-line parsing.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/issues/215#issuecomment-3367499147) <!-- digest:efa0abaa746a70d8ffc892081f4897113abea8d9e772d403cf0bfeb08ef6df67 -->

- Decision (Completed) — 2025-10-03 by @dutchsloot84
  Keep **backwards compatibility**: inline single-line markers remain valid; the collector parses both.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/issues/215#issuecomment-3367499147) <!-- digest:fd7930cbfbe6a49709741b062c8ed0c05763ed6fcc360fcbcd41e221cce2692f -->

- Decision (Completed) — 2025-10-03 by @dutchsloot84
  Normalize output to **indented, multi-line bullets** in mirrored notes to preserve human readability.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/issues/215#issuecomment-3367499147) <!-- digest:81f315552b7bf116e733efe51efe28f074857486463274b4fa55c1bbc04cf081 -->

- Note (Completed) — 2025-10-03 by @dutchsloot84
  Parser handles nested bullets and wrapped lines; leading `- ` or `* ` are supported.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/issues/215#issuecomment-3367499147) <!-- digest:f41a669ebacaaad861b463dc7208b84d47fe1113efe1b70e6badebb1a742cebc -->

- Note (Completed) — 2025-10-03 by @dutchsloot84
  Deduping is by (type, text, source URL, date); identical entries won’t be mirrored twice.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/issues/215#issuecomment-3367499147) <!-- digest:e8bd9823a41e2e1190b9058a598b68995ed5349660bdd57bd49cd3b661a4adbc -->

- Note (Completed) — 2025-10-03 by @dutchsloot84
  Performance: parsing added ~O(n) per comment; negligible at current repo scale.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/issues/215#issuecomment-3367499147) <!-- digest:4dc201dcc0a8c911c9918ffe16bbc38f042229be5f3964669b1804d2578b9384 -->

- Action (Completed) — 2025-10-03 by @dutchsloot84
  (Owner: Shayne) Add the **Marker Guide** link to the PR/Issue templates’ help text by **EOW**.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/issues/215#issuecomment-3367499147) <!-- digest:cae31433d236500412870e0de65e0d957c65d1866fb5b932501de112206b5245 -->

- Action (Completed) — 2025-10-03 by @dutchsloot84
  (Owner: Shayne) Run the Historian job manually on `main` to verify end-to-end mirroring **today**.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/issues/215#issuecomment-3367499147) <!-- digest:efba582018ddb819f7bd9acb40c456f874de6e032521b397fec1130291b6e407 -->

- Action (Completed) — 2025-10-03 by @dutchsloot84
  (Owner: Shayne) Post a one-time FYI in the **Contributing** doc introducing the new block style **today**.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/issues/215#issuecomment-3367499147) <!-- digest:82f8bde1c6e8a0c902a94c8b9e6dc32c725bb0a931d6738e4f9fdea3570b38ba -->

# Notes & Decisions — #137 Major Historian Module Enhancements, Stability Fixes, and Documentation Updates

_Repo:_ dutchsloot84/ReleaseCopilot-AI
_Source:_ https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/137

- Decision (Uncategorized) — 2025-09-26 by @dutchsloot84
  Historian will only be invoked via `python -m scripts.generate_history` with `PYTHONPATH` set; direct `python scripts/...` is deprecated.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/137#issuecomment-3340633705) <!-- digest:901c95e93fb10bd82c435274d845c465d84b302ef58fab7bc2858efb6ec9a276 -->

- Decision (Uncategorized) — 2025-09-26 by @dutchsloot84
  Notes-mirror promotes PR/Issue markers [Decision|Note|Blocker|Action] into the weekly history ledger.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/137#issuecomment-3340633705) <!-- digest:cd27699d61fa42e92dabb2043403bfa8644e33de1d2d5a2a994a3468baedef3c -->

- Note (Uncategorized) — 2025-09-26 by @dutchsloot84
  Added `--debug-scan` and guarded `--since/--until`; updated collectors/templates; Windows-compatible `until` support.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/137#issuecomment-3340633705) <!-- digest:ba05b6749ed1a1d76571e83f1190c56d29992ea94dc83f40c55cfe31aa6fc2f0 -->

- Action (Uncategorized) — 2025-09-26 by @dutchsloot84
  (Owner: Shayne) Update the weekly Historian workflow to the module invocation and ensure `permissions: { pull-requests: read, issues: read, contents: read }` before the next scheduled run.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/137#issuecomment-3340633705) <!-- digest:664fc76270832473fef3e0fca125d5f69459a4240595922447f098c4d9412324 -->

- Action (Uncategorized) — 2025-09-26 by @dutchsloot84
  (Owner: Shayne) Run a local dry run to confirm marker capture: `python -m scripts.generate_history --since 10d --until now --output docs/history --debug-scan` and check the scan log for this comment.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/137#issuecomment-3340633705) <!-- digest:69393b4c5473f73df03fcd777dcfaecfa9cbe5a06fd1523c0ca435c4f1d24bc8 -->

- Blocker (Uncategorized) — 2025-09-26 by @dutchsloot84
  If the scheduled run still uses the old entrypoint or lacks PR read permissions, marker collection will be incomplete; fix workflow invocation/permissions first.
  [View comment](https://github.com/dutchsloot84/ReleaseCopilot-AI/pull/137#issuecomment-3340633705) <!-- digest:6e6cecd53509da2f932a9ba900291721f75e9cb1311b6fad311cf65fb9a9985b -->

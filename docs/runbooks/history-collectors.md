# Historian Collectors & Notes Mirroring

This runbook explains how to configure the Git Historian collectors and the Notes & Decisions mirroring add-on.

## Notes & Decisions collector

The Notes collector scans comments for configured markers (Decision:, Note:, Blocker:, Action:). You can tune the behaviour in `config/defaults.yml` under `historian.sources.notes`:

```yaml
historian:
  sources:
    notes:
      scan_issue_comments: true
      scan_pr_comments: true
      scan_notes_files: true
      notes_glob: "docs/history/notes/**/*.md"
      comment_markers: ["Decision:", "Note:", "Blocker:", "Action:"]
      annotate_group: true
```

* `scan_notes_files` controls whether the section surfaces the configured notes directory in the rendered filters so readers know where mirrored files land.
* `annotate_group` adds the Completed / In Progress / Backlog annotation to each entry.

## Notes file mirroring

Enable mirroring with the top-level configuration block:

```yaml
historian:
  notes_file_mirroring:
    enabled: true
    repo_root: "."
    output_dir: "docs/history/notes"
    dry_run: false
    annotate_group: true
```

* `repo_root` is resolved relative to the Historian `--root` argument. Leave it at `.` for the repository root.
* `output_dir` determines where mirrored files are written. The Historian run will create the directory if it does not exist.
* `dry_run: true` will skip writes while logging the files that would change.
* `annotate_group` mirrors the group status (Completed / In Progress / Backlog) into the file entries.

### File naming & format

Each mirrored comment line is appended to a file named:

```
<YYYY-MM-DD>-<owner>-<repo>-<number>.md
```

Example entry:

```
- Decision (In Progress) — 2025-09-26 by @octocat
  Adopt webhook-based sync to reduce polling.
  [View comment](https://github.com/.../issues/1234#issuecomment-...)
```

A hidden digest marker (`<!-- digest:... -->`) is written next to the comment link to ensure repeated runs remain idempotent.

### Searching the ledger

* Use the digest comment to deduplicate manual edits.
* The `_Repo_` and `_Source_` metadata at the top of each file allow quick filtering in editors or `rg`.
* Combine the glob from `notes_glob` with `rg "Decision \(In Progress\)" docs/history/notes` to find all active decisions.

### Rollback

To disable mirroring, set `notes_file_mirroring.enabled: false` and rerun Historian. To remove mirrored entries, delete the affected files under `docs/history/notes/` and rerun the workflow.

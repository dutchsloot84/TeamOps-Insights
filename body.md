## Summary
Add a baseline CI pipeline that runs lint/tests, builds the Lambda artifact, and performs a CDK synth on every PR/push; and add an S3 uploader module that pushes audit artifacts (JSON/Excel + raw payloads) to a bucket under a versioned prefix `<prefix>/<fix-version>/<YYYY-MM-DD_HHMMSS>/...`.

This formalizes our automation path and ensures every change is tested, packaged, and infra-valid before merge. It also standardizes how reports are published for UI consumption and downstream tools.

## Why this matters
- **Fast feedback:** Catch regressions early (lint/tests) and infra drift (cdk synth).
- **Repeatable packaging:** Guarantees deployable Lambda bundles exist on demand.
- **Consistent publishing:** S3 layout makes it easy to browse runs by fix version and timestamp; unlocks the Streamlit UI picker and “compare” workflows.

## Scope
1) **CI pipeline (GitHub Actions)**
   - Triggers: PRs to `main`, pushes to `main` and `feature/**`, `workflow_dispatch`, tags `v*.*.*`.
   - Jobs:
     - `python-checks`: set up Python 3.11, install deps, run linter (ruff/flake8) + `pytest -q`.
     - `package`: build Lambda bundle via packaging helper (fallback to zip) and upload as artifact.
     - `cdk-synth`: install CDK and run `cdk synth` (no deploy).
   - Caching: pip cache.
   - Artifacts: `lambda_bundle.zip` on PRs; tagged artifacts named with the tag.

2) **S3 uploader**
   - New module: `src/releasecopilot/uploader.py` with:
     - `build_versioned_prefix(base_prefix, fix_version, when) -> "<base>/<fix>/<YYYY-MM-DD_HHMMSS>"`
     - `upload_directory(bucket, base_prefix, local_dir, subdir, metadata)`
   - CLI flags/env:
     - `--s3-bucket` (or `RC_S3_BUCKET`) optional.
     - `--s3-prefix` (or `RC_S3_PREFIX`, default `releasecopilot`).
   - Behavior:
     - After export completes, if bucket provided, upload:
       - `reports/` → `s3://bucket/<prefix>/<fix>/<ts>/reports/...`
       - `raw/`     → `s3://bucket/<prefix>/<fix>/<ts>/raw/...`
     - Use SSE-S3; add metadata: `fix-version`, `generated-at`, `git-sha` (if available).
     - Log clear success/fail; skip gracefully if unset.

## Out of scope
- CDK deploy or environment promotion (separate release workflow).
- Step Functions orchestration.

## Acceptance Criteria
- **CI:** On PRs/pushes, lints run, tests pass, Lambda bundle is built, and `cdk synth` succeeds.
- **Artifacts:** `lambda_bundle.zip` downloadable from CI; tagged builds store versioned artifact.
- **Uploader:** Running the CLI with `--s3-bucket my-bkt --s3-prefix audits --fix-version 2025.10.24` creates keys:
  - `s3://my-bkt/audits/2025.10.24/<YYYY-MM-DD_HHMMSS>/reports/...`
  - `s3://my-bkt/audits/2025.10.24/<YYYY-MM-DD_HHMMSS>/raw/...`
- **Docs:** README has “CI pipeline” + “S3 upload layout” sections with examples.

## Risks & mitigation
- **IAM scope too broad:** Limit to specific bucket prefix ARNs.
- **Timestamp nondeterminism:** Always use UTC and single timestamp for a run.
- **Missing bucket/creds:** Skip upload with INFO log, do not fail the audit.

## Implementation plan
- Add `.github/workflows/ci.yml` (see Codex prompt below).
- Add `src/releasecopilot/uploader.py` + minimal unit tests for prefix builder.
- Wire new flags into CLI; ensure exporter calls uploader conditionally.
- Update README with examples; note required AWS permissions (PutObject to prefix, SSE-S3).

---

## Codex prompt (implementation helper)

You are updating ReleaseCopilot-AI to add CI and an S3 uploader.

**Deliverables**
1) `.github/workflows/ci.yml` that:
   - Triggers on push (main, feature/**), PRs to main, tags `v*.*.*`, and workflow_dispatch.
   - Job `python-checks`: Python 3.11, cache pip, install deps, run `ruff check` and `pytest -q`.
   - Job `package`: build Lambda bundle via packaging helper (`scripts/package_lambda.*` if present; fallback to zipping `src/`), upload as artifact.
   - Job `cdk-synth`: install aws-cdk v2, run `cdk synth` in `infra/cdk` (adjust path if different).
   - Upload artifacts on PRs and versioned artifacts on tags.

2) `src/releasecopilot/uploader.py` exposing:
   - `build_versioned_prefix(base_prefix: str, fix_version: str, when: datetime|None) -> str`
   - `upload_directory(bucket: str, base_prefix: str, local_dir: Path, subdir: str, extra_metadata: dict|None) -> Iterable[str]`
   - Internals use `boto3` with SSE-S3 and guessed `ContentType`. Add a small unit test for `build_versioned_prefix`.

3) CLI wiring:
   - Add flags `--s3-bucket` and `--s3-prefix` (env fallbacks `RC_S3_BUCKET`, `RC_S3_PREFIX`).
   - After export, if bucket is set, call uploader to push `reports/` and `raw/` directories under the run prefix.
   - Log counts of uploaded files and the base S3 URI.

4) Docs:
   - Append to README: “CI pipeline” and “S3 upload layout” sections with example commands and tree structure.

**Constraints**
- Keep CI deploy-free (synth only).
- Use UTC for timestamp; metadata includes `fix-version` and `generated-at`.
- Fail gracefully when upload is skipped or AWS creds are missing.

**Acceptance**
- CI passes on a branch and PR; tagged run uploads artifact.
- Local CLI with S3 flags produces the expected S3 key layout and logs.

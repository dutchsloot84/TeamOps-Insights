# CDK Workflow Preflight Checklist

The `cdk-ci` GitHub Actions workflow now performs an explicit preflight before
running `cdk list`, `cdk synth`, or other AWS CDK commands. The preflight steps
ensure the CDK application can be located and executed reliably in CI and make
troubleshooting failures easier for contributors.

## What the preflight checks

1. **Repository layout** – The workflow prints the workspace root, lists its
   contents, and confirms the git top-level directory. These diagnostics make it
   obvious when the runner is in an unexpected folder.
2. **CDK app discovery** – In `infra/cdk` the workflow:
   - Dumps the directory contents
   - Verifies that `cdk.json` exists
   - Uses `jq` to confirm the `app` key is present and non-empty, printing the
     resolved command.
   If the file is missing or the `app` key is blank, the job fails with an
   actionable error instead of the generic `Did you mean ack?` banner.
3. **Language dependencies** – For the Python CDK app the workflow installs
   requirements from `requirements.txt` (and `requirements-dev.txt` when
   available) before calling `npx aws-cdk@2`. The structure supports Node-based
   apps through the `hashFiles` guard should the repository add a `package.json`
   in the future.
4. **Environment sanity** – The workflow runs `npx -y aws-cdk@2 cdk --version`
   and `cdk doctor`, emitting the CDK context file when present.
5. **Verbose listing fallback** – `cdk list` now runs with `-v` and, if it
   fails, automatically retries with an explicit `-a "<app command>"` so the
   logs show exactly which command CDK tried to execute.

## Local debugging tips

Run the same checks locally from the repository root:

```bash
cd infra/cdk
ls -la
cat cdk.json
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/preflight.py
npx -y aws-cdk@2 cdk -v list
```

If the verbose `cdk list` fails locally, copy the `app` command printed from
`cdk.json` and execute it directly (for example `python infra/cdk/run_cdk_app.py`) to
see any underlying stack trace before retrying the CDK CLI.

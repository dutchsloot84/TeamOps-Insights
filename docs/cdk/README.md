# CDK Best Practices (This Repo)

> **Run all AWS CDK commands from the repository root.**

The infrastructure code is designed so that every `npx cdk` invocation occurs at the top level of the repository. The root-level [`cdk.json`](../../cdk.json) exposes a module-style entry point that keeps local development and CI perfectly aligned.

## Layout expectations

- `cdk.json` (at the repository root) contains:

  ```json
  {
    "app": "python -m infra.cdk.app"
  }
  ```
- The CDK application module lives in [`infra/cdk/app.py`](../../infra/cdk/app.py) and must remain importable via `python -m infra.cdk.app`.
- `infra/cdk/__init__.py` exists (even if empty) so `infra.cdk` is treated as a proper Python package.
- Application code uses absolute imports, e.g. `from infra.cdk.core_stack import CoreStack`.

Keeping this layout prevents the classic "`--app` is required" error that appears when CDK is executed outside the repository root or when multiple `cdk.json` files are present.

## Dependencies

Install AWS CDK v2 and supporting libraries from [`infra/cdk/requirements.txt`](../../infra/cdk/requirements.txt):

```text
aws-cdk-lib>=2.150.0,<3.0.0
constructs>=10.0.0,<11.0.0
boto3>=1.28.0
```

These packages provide the `aws_cdk` namespace, construct primitives, and optional AWS API clients used by the app. Upgrade or pin additional dependencies in the same file so every environment (local shells, CI, automation) shares the exact toolchain.

## Local quickstart

```bash
python -m venv .venv
# PowerShell: .\.venv\Scripts\Activate.ps1
# Bash / Zsh: source .venv/bin/activate
python -m pip install -U pip
pip install -r infra/cdk/requirements.txt
npx cdk list
npx cdk synth
```

Running the commands from the repository root guarantees that CDK discovers `cdk.json`, resolves the `python -m infra.cdk.app` entry, and loads the `infra.cdk` package without import hacks.

## Continuous integration summary

- All CI jobs operate from the repository root—no `cd infra/cdk` steps.
- Workflows provision Node.js 20 LTS (satisfying jsii requirements) and Python 3.11.
- A virtual environment installs `infra/cdk/requirements.txt` before invoking `npx cdk ...`.
- Optional guardrails can print the working directory and `cdk.json` contents to diagnose misconfigurations.

## Avoid these pitfalls

- ❌ Adding another `cdk.json` inside `infra/cdk/` or elsewhere.
- ❌ Passing random `-a` paths that diverge from the module entry.
- ❌ `cd`-ing into `infra/cdk` (or any subdirectory) before running CDK CLI commands.
- ❌ Using relative imports or missing `__init__.py` files that break module resolution.

Stick to the root-centric workflow and CDK will consistently discover the app, both locally and inside GitHub Actions.

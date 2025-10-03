# ADR-0001: Adopt root-level `cdk.json` with module entry

## Status
Accepted

## Context
Repeated CI failures reported `--app is required either in command-line, in cdk.json or in ~/.cdk.json`. Historical workflows executed `cdk` commands from `infra/cdk/`, carried duplicate `cdk.json` files, and occasionally passed bespoke `-a` paths. Those patterns diverged from AWS CDK defaults and caused the CLI to miss the intended entry point. Contributors also hit `ModuleNotFoundError` exceptions because the `infra` package was not initialised properly before running `python infra/cdk/app.py`.

## Decision
- Maintain a single `cdk.json` at the repository root with `"app": "python -m infra.cdk.app"`.
- Treat `infra` as an installable package (`infra/__init__.py`, `infra/cdk/__init__.py`) and require absolute imports such as `from infra.cdk.core_stack import CoreStack`.
- Run every CDK command (`npx cdk list`, `synth`, `diff`, `deploy`) from the repository root, locally and in GitHub Actions.
- Provision dependencies through `infra/cdk/requirements.txt` and install them before invoking the CDK CLI.

## Consequences
- CI and local environments share the same entrypoint resolution, eliminating the `--app` discovery errors.
- The workflows simplify to a single virtual environment and Node 20 toolchain, making synth/diff/deploy deterministic.
- Documentation can reference one canonical set of commands, reducing onboarding friction.
- Guardrails (diagnostic steps) highlight when someone attempts to run CDK from the wrong directory or removes the root `cdk.json`.

## Alternatives considered
- **Nested `cdk.json` files** inside `infra/cdk/`: rejected because the CLI would still require directory hopping and often conflicted with the root config.
- **Passing `-a` paths everywhere**: rejected as brittle; forgetting the flag reproduces the original error and contradicts CDK's discovery model.
- **Custom wrapper scripts** to set `APP`: rejected to keep the workflow aligned with standard CDK usage and reduce bespoke tooling.

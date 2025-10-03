# CDK Infrastructure

The AWS CDK application for ReleaseCopilot is configured via the repository root `cdk.json`. GitHub Actions relies on the
standard CDK CLI auto-discovery, so no additional wrappers or location checks are required. Keep the root file in sync with
any entry point changes (for example `infra/cdk/run_cdk_app.py`) to ensure CI and local commands behave the same way.

Local commands such as `cdk synth` or `cdk deploy` can be executed from the repository root without supplying `-a`. The
workflow installs the dependencies defined in `infra/cdk/requirements.txt` and then runs the CDK CLI directly.

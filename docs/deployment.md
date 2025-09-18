# Deployment Guide

This guide covers deploying ReleaseCopilot-AI workloads and infrastructure.

## Application Containers

Local development uses Docker Compose (`docker-compose.yml`) to orchestrate
services for integration testing. Refer to the root README for detailed steps.

## AWS CDK Deployment

### Prerequisites

- AWS account with permissions to deploy the stacks.
- Python 3.12 and AWS CDK v2 installed.
- Bootstrapped environment: `cdk bootstrap`.

### Local Workflow

```bash
cd cdk
pip install -r requirements.txt
cdk synth
cdk diff
cdk deploy --all
```

Enable the optional EventBridge schedule when deploying the Lambda stack:

```bash
ENABLE_EVENTBRIDGE=1 cdk deploy releasecopilot-ai-lambda
```

### Continuous Integration

- **cdk-ci**: runs on pull requests and pushes to `main`. Synthesises and diffs
  the stacks without deploying.
- **cdk-deploy**: manual `workflow_dispatch` gated by the `aws-deploy`
  environment. The workflow configures AWS credentials via OIDC and deploys the
  stacks. Provide the `AWS_OIDC_ROLE_ARN` secret scoped to that environment.

### Runtime Settings

- Artifacts bucket, secret ARN, and execution role ARNs are exported as stack
  outputs when deploying the core stack.
- The Lambda stack consumes `ARTIFACTS_BUCKET`, `OAUTH_SECRET_ARN`, and
  `PROJECT_NAME` environment variables to orchestrate the audit workflow.
- Toggle the EventBridge schedule by setting `ENABLE_EVENTBRIDGE=1` during
  deployment; the rule is created but disabled by default.

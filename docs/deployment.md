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
cd infra/cdk
pip install -r requirements.txt
cdk synth
cdk diff
cdk deploy ReleaseCopilot-<env>-Core
```

> **Tip:** The `<env>` context defaults to `dev`. Override it with `cdk synth -c env=staging` (or any other value) to produce a differently named stack.

The unified `ReleaseCopilot-<env>-Core` stack provisions:

- An artifacts S3 bucket (`ArtifactsBucket`) scoped to the account, with lifecycle
  rules for raw and report prefixes.
- Secrets Manager secrets for Jira, Bitbucket, and an optional webhook signing
  secret, reused across runtimes when ARNs are not supplied via context.
- A Python 3.11 ReleaseCopilot Lambda function plus API Gateway, DynamoDB table,
  and reconciliation/background Lambda components.
- CloudWatch alarms, optional EventBridge schedules, and SQS DLQ support for the
  reconciliation workflow.

Enable the optional EventBridge driven sync during deployment by passing the CDK
context flag:

```bash
cdk deploy ReleaseCopilot-<env>-Core -c scheduleEnabled=true
```

### Continuous Integration

- **CI (`cdk-synth` job)**: synthesises the CDK app on every pull request and
  push to `main`, ensuring the stack definition remains valid.
- **cdk-deploy**: manual `workflow_dispatch` gated by the `aws-deploy`
  environment. The workflow configures AWS credentials via OIDC and deploys the
  core stack. Provide the `AWS_OIDC_ROLE_ARN` secret scoped to that environment.

### Runtime Settings

- Stack outputs expose the artifacts bucket name, Lambda identifiers, DynamoDB
  table, webhook URL, and reconciliation Lambda name for downstream integration.
- The ReleaseCopilot Lambda receives `RC_S3_BUCKET`, `RC_S3_PREFIX`, and
  `RC_USE_AWS_SECRETS_MANAGER` environment variables and looks up Jira/Bitbucket
  OAuth credentials from Secrets Manager.
- The reconciliation job exports `TABLE_NAME`, `JIRA_BASE_URL`,
  `RC_DDB_MAX_ATTEMPTS`, `RC_DDB_BASE_DELAY`, `METRICS_NAMESPACE`, and
  `JIRA_SECRET_ARN`, with optional `FIX_VERSIONS` and `JQL_TEMPLATE` values when
  provided via context.
- Jira webhook processing is powered by `TABLE_NAME`, `LOG_LEVEL`, and optional
  `WEBHOOK_SECRET_ARN` environment variables surfaced by the stack.
- Enable or disable the EventBridge schedules via the `scheduleEnabled=true` and
  `reconciliationScheduleEnabled=false` context flags during synth/deploy. If a
  `scheduleCron` or `reconciliationCron` expression is provided, those override
  the default rate expressions.

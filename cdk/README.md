# releasecopilot-ai AWS CDK App

This CDK application provisions the core infrastructure required to execute the
release audit workflow.

## Prerequisites

- Python 3.12
- AWS credentials (via profile or OIDC)
- Bootstrapped environment: `cdk bootstrap`

Install dependencies once:

```bash
pip install -r requirements.txt
```

## Useful Commands

```bash
cdk synth        # emits the CloudFormation templates
cdk diff         # compares against deployed stacks
cdk deploy --all # deploys both stacks
```

To enable the optional EventBridge schedule during deploy:

```bash
ENABLE_EVENTBRIDGE=1 cdk deploy releasecopilot-ai-lambda
```

## Stacks

- **CoreStack** – S3 bucket, Secrets Manager secret, execution roles, and outputs.
- **LambdaStack** – Audit Lambda function packaged from `dist/lambda` and the
  (disabled by default) EventBridge rule.

Before deploying Lambda run `scripts/package_lambda.sh` to refresh the assets.

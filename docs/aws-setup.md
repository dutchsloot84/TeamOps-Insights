# AWS baseline and CDK migration

## Manual setup recap

The initial Release Copilot proof-of-concept relied on a manually provisioned IAM execution role with temporary `AdministratorAccess`/`FullAccess` policies, an S3 bucket configured for artifact storage, and Secrets Manager entries for Jira and Bitbucket OAuth credentials. Those steps enabled the prototype but left broad permissions in place and required console-driven configuration management.

## CDK-managed equivalent

The new CDK `CoreStack` codifies those resources with least-privilege defaults:

- **S3 artifacts bucket** &mdash; server-side encrypted with AWS-managed keys, versioned, and non-public. Lifecycle management moves `raw/` objects to Standard-IA after 30 days and deletes them after 90 days, while `reports/` objects move to Standard-IA after 60 days and are retained indefinitely.
- **Secrets** &mdash; existing Jira and Bitbucket secrets can be imported by ARN; when omitted the stack creates placeholders using `SecretStringGenerator` so synthesis/deployment succeed without pre-provisioned secrets.
- **Lambda execution role** &mdash; grants only the actions required to write logs, list the bucket within the `releasecopilot/` prefix, read/write prefixed objects, and fetch the two exact secrets. The Lambda receives environment variables (`RC_S3_BUCKET`, `RC_S3_PREFIX`, `RC_USE_AWS_SECRETS_MANAGER`) that mirror the manual configuration but are now centrally defined.
- **Outputs** &mdash; expose the bucket name and Lambda identifiers for downstream wiring. Future enhancements (for example an EventBridge schedule driven by `scheduleEnabled`/`scheduleCron` context flags) can attach to the Lambda without altering these foundations.

## Migration guidance

1. Deploy the CDK stack in a sandbox account and validate artifact uploads, secret retrieval, and Lambda execution logs.
2. Once validated, deploy to the production account. The stack will create or import the necessary secrets, enforce lifecycle policies, and provision the least-privilege execution role.
3. After the production deployment is confirmed, detach the temporary `FullAccess` policies from the original console-managed role or switch workloads to the CDK-managed role entirely.

## Quick runbook

```bash
# one-time setup
cd infra/cdk
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\Activate
pip install -r requirements.txt
cdk bootstrap

# synth & test
pytest -q
cdk synth

# deploy with defaults
cdk deploy --require-approval never

# override context for real bucket + secrets
cdk deploy \
  --context region=us-west-2 \
  --context bucketName=releasecopilot-artifacts-slv \
  --context jiraSecretArn=arn:aws:secretsmanager:us-west-2:ACCOUNT:secret:/releasecopilot/jira-XXXX \
  --context bitbucketSecretArn=arn:aws:secretsmanager:us-west-2:ACCOUNT:secret:/releasecopilot/bitbucket-YYYY
```

### Quick runbook: CloudWatch alarms

```bash
cd infra/cdk
source .venv/bin/activate  # Windows: .venv\Scripts\Activate
cdk synth

# deploy without email
cdk deploy --require-approval never

# deploy with email notifications
cdk deploy --context alarmEmail=you@example.com --require-approval never

# smoke test: cause a Lambda error, re-invoke, then check CloudWatch Alarms
```

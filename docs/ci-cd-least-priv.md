# Least-Privilege CDK Deployments

This guide walks through the path from the initial broad-deployment permissions to a locked-down IAM role driven by inline policies.

## Policy artifacts

The repository provides policy templates under `infra/iam/policies/`:

* `cfn.json` – CloudFormation permissions scoped to `arn:aws:cloudformation:${aws:Region}:${aws:AccountId}:stack/ReleaseCopilot-*/*`.
* `s3_bootstrap.json` – Grants access to the bootstrap bucket `cdk-hnb659fds-assets-${aws:AccountId}-${aws:Region}` for publishing CDK assets.
* `logs.json` – Initial wildcard permissions for Lambda log groups prefixed with `/aws/lambda/releasecopilot-*`.
* `dynamodb.json` – Access to the `ReleaseCopilot-Reports` table and any secondary indexes.
* `secrets.json` – Manage Secrets Manager secrets prefixed with `releasecopilot/`.
* `passrole.json` – Allows passing IAM roles named `ReleaseCopilot-*`.

These templates use `${aws:AccountId}` and `${aws:Region}` variables so they can be attached directly as inline policies or further refined.

## Core stack updates

The `infra/cdk/core_stack.CoreStack` execution role now enumerates the specific CloudWatch log group ARNs that it writes to instead of relying on the `/aws/lambda/*` wildcard. Record those ARNs from discovery or `cdk synth` output and update `infra/iam/resources.json` so the generated `logs.least-priv.json` reflects the restricted scope. The legacy CDK entry point in `cdk/stacks/core_stack.py` is kept for historical reference only and should be treated as deprecated.

## Generating least-privilege variants

Once the diagnostic job has reported the exact resource names, populate `infra/iam/resources.json` with the concrete values (log groups, DynamoDB tables, secrets, roles). Then run:

```bash
python scripts/compose_policies.py --resources infra/iam/resources.json --output-dir infra/iam/policies/generated
```

The script writes files such as `logs.least-priv.json` and `dynamodb.least-priv.json` in the `generated/` directory with resources narrowed to those discovered at runtime.

## Attaching the inline policies

Assuming the deploy role ARN is available in `${ROLE_ARN}`, attach the policies in order:

```bash
aws iam put-role-policy --role-name <deploy-role-name> --policy-name ReleaseCopilotCloudFormation --policy-document file://infra/iam/policies/cfn.json
aws iam put-role-policy --role-name <deploy-role-name> --policy-name ReleaseCopilotBootstrap --policy-document file://infra/iam/policies/s3_bootstrap.json
aws iam put-role-policy --role-name <deploy-role-name> --policy-name ReleaseCopilotLogs --policy-document file://infra/iam/policies/generated/logs.least-priv.json
aws iam put-role-policy --role-name <deploy-role-name> --policy-name ReleaseCopilotDynamoDB --policy-document file://infra/iam/policies/generated/dynamodb.least-priv.json
aws iam put-role-policy --role-name <deploy-role-name> --policy-name ReleaseCopilotSecrets --policy-document file://infra/iam/policies/generated/secrets.least-priv.json
aws iam put-role-policy --role-name <deploy-role-name> --policy-name ReleaseCopilotPassRole --policy-document file://infra/iam/policies/generated/passrole.least-priv.json
```

> **Tip:** Replace the `generated/` file paths with the base templates while the diagnostic job is still running. Once the least-privilege data is known, regenerate and re-run the commands above.

## Detaching broad managed policies

After the inline policies are in place, remove the managed policies that were used for the bootstrap deploy:

```bash
aws iam detach-role-policy --role-name <deploy-role-name> --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsFullAccess
aws iam detach-role-policy --role-name <deploy-role-name> --policy-arn arn:aws:iam::aws:policy/SecretsManagerReadWrite
aws iam detach-role-policy --role-name <deploy-role-name> --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBReadOnlyAccess
```

Re-run the `cdk-ci` workflow (or `npm run cdk:deploy`) to confirm that deploys succeed with the inline policies only. Keep the diagnostic job enabled until you have validated at least one successful deployment with the restricted permissions.

## Historian

* **Decisions** – Store reusable inline policy JSON in the repository and use `scripts/compose_policies.py` to tailor resource ARNs.
* **Notes** – `infra/iam/resources.json` should be updated after each diagnostic run so the generated policies stay aligned with deployed resources.
* **Actions** – Remove the diagnostic job from `.github/workflows/cdk-ci.yml` once least-privilege enforcement is validated.

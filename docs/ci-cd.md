# CI/CD runbook for CDK deployments

This runbook explains how the `cdk-ci` workflow deploys the infrastructure stacks and what to check when something fails.

## Workflow overview
- **Triggers** – Pull requests touching `infra/**`, `cdk/**`, `cdk.json`, `package*.json`, or `requirements*.txt` run the `CDK diff` job. Pushes to `main` or tags that start with `v` run both `CDK diff` and `CDK deploy`.
- **Credentials** – The workflow assumes the GitHub OIDC role via `${{ vars.OIDC_ROLE_ARN }}` (falling back to the secret of the same name). The AWS Region defaults to `us-west-2` but can be overridden through the `AWS_REGION` repository variable.
- **Build pipeline** – Each job installs CDK dependencies, packages the Lambda code with `scripts/package_lambda.sh`, runs `cdk synth`, and keeps the synthesized templates (`cdk.out`) as an artifact. Deployments run `cdk deploy --require-approval never` for `releasecopilot-ai-core` and `releasecopilot-ai-lambda`.
- **Non-blocking diffs** – On pull requests, the `cdk-diff` job is marked as informational so reviewers still see results even if the diff fails because of missing AWS permissions or template drift.

## Rerunning or debugging jobs
1. Open the workflow run in GitHub Actions and use **Re-run job** (preferred) or **Re-run all jobs** after pushing policy fixes.
2. Inspect the uploaded `cdk.out` artifact to confirm CDK generated the expected assets.
3. When the workflow fails before `configure-aws-credentials`, the issue is in dependency installation (Python, Node, packaging). When it fails after that step, collect the AWS error message and adjust the IAM policy or AWS environment.
4. If the `cdk-diff` job reports empty `cdk.out`, ensure `scripts/package_lambda.sh` succeeded and that `dist/lambda` contains the packaged runtime before running CDK commands.

## Common errors and fixes
| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `AccessDenied` on `sts:AssumeRole` | Repository variable `OIDC_ROLE_ARN` missing or trust policy not scoped to this repo | Set `OIDC_ROLE_ARN` in repo variables and confirm the IAM trust policy includes `repo:dutchsloot84/ReleaseCopilot-AI:*`.
| `AccessDenied` on `s3:PutObject` | Bootstrap bucket policy missing | Attach the `BootstrapBucketObjectsRW` statement from `infra/iam/github-actions-oidc-permissions.json` to the role and verify the CDK qualifier (`hnb659fds` by default).
| `AccessDenied` on `cloudformation:*` | Stack ARN pattern mismatch | Ensure the CloudFormation statement uses the `ReleaseCopilot-*` prefix or adjust it to match your stack names.
| `ResourceNotFoundException` while packaging Lambda | Dependencies in `requirements.txt` changed | Update the workflow cache or run `scripts/package_lambda.sh` locally to confirm the bundle builds.

## Values to verify in AWS
- [ ] GitHub OIDC provider: `token.actions.githubusercontent.com` with `aud=sts.amazonaws.com` and `sub=repo:dutchsloot84/ReleaseCopilot-AI:*`.
- [ ] IAM role session duration (60–120 minutes) allows CDK deploys to finish.
- [ ] CDK bootstrap stack exists in `us-west-2` and the bucket name matches `cdk-hnb659fds-assets-<account>-us-west-2` (update the policy if your qualifier differs).
- [ ] Actual log group names for Lambda functions (expected `/aws/lambda/releasecopilot-*`).
- [ ] DynamoDB table name and GSIs used by ReleaseCopilot (expected `ReleaseCopilot-Reports` and its secondary indexes).
- [ ] Secrets Manager prefix used at runtime (expected `releasecopilot/*`).

## What you need to verify/do manually
- [ ] Detach the broad managed policies from the GitHub OIDC deployment role and attach the inline policy defined in `infra/iam/github-actions-oidc-permissions.json`.
- [ ] Update the inline policy if your CDK qualifier is not `hnb659fds` or if stack/resource names use a different prefix.
- [ ] Set the `OIDC_ROLE_ARN` repository variable (or secret) so the workflow can assume the deployment role.
- [ ] Run the `cdk-ci` workflow on `main` or a `v*` tag and capture the run URL/screenshot for the issue tracker.
- [ ] Grant any additional scoped permissions surfaced by the first failed deploy attempt (for example, IAM role updates for new resources).

## Additional notes
- The IAM policy template intentionally scopes IAM, DynamoDB, Secrets Manager, CloudWatch Logs, and S3 permissions to ReleaseCopilot resources. Adjust the ARNs if you rename stacks or tables.
- If you introduce Docker or ECR assets in CDK, extend the policy with the minimal `ecr:*` and `ecs:*` permissions required by those assets.
- For staging or multi-account setups, duplicate the workflow with different `AWS_REGION`, `PROJECT_NAME`, and `OIDC_ROLE_ARN` variables rather than broadening this policy.

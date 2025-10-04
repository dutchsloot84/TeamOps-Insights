# ReleaseCopilot Readiness Smoke

This runbook documents the lightweight readiness probe exposed by `rc health --readiness`. The
command validates AWS Secrets Manager access, DynamoDB connectivity, webhook secret resolution, and
S3 write/delete permissions. The output is deterministic JSON suitable for CI gates and Historian
artifacts.

## When to Run

- Before deploying webhook ingest, reconciliation, or audit jobs to a new AWS account.
- As a CI smoke check in release pipelines.
- On-demand when rotating secrets or modifying IAM policies.

## Invocation

```bash
rc health --readiness --json dist/health.json
```

Optional flags:

| Flag | Description |
| ---- | ----------- |
| `--bucket s3://bucket/prefix` | Override the bucket/prefix used for the S3 sentinel object. |
| `--table TABLE` | Override the DynamoDB table checked for write/delete access. |
| `--secrets name1,name2` | Restrict the secret identifiers to validate. Names are looked up from `config/settings.yaml`; unknown entries are treated as literal ARNs. |
| `--dry-run` | Show the execution plan without calling AWS services. |
| `--json PATH` | Write readiness output to `PATH` instead of stdout. |
| `--config PATH` | Override the settings file used for defaults. |
| `--log-level LEVEL` | Adjust logging verbosity (defaults to `INFO`). |

### Sample Output

```json
{
  "version": "health.v1",
  "timestamp": "2024-05-01T12:00:00Z",
  "overall": "pass",
  "checks": {
    "secrets": {
      "status": "pass",
      "resource": "secretsmanager://jira=secret/jira, webhook=secret/webhook"
    },
    "dynamodb": {
      "status": "pass",
      "resource": "dynamodb://releasecopilot-jira-cache"
    },
    "s3": {
      "status": "pass",
      "resource": "s3://releasecopilot-artifacts/readiness/health/readiness/abc123.txt"
    },
    "webhook_secret": {
      "status": "pass",
      "resource": "secretsmanager://secret/webhook"
    }
  }
}
```

## JSON Contract

The output conforms to [`docs/schemas/health.v1.json`](../schemas/health.v1.json). The schema is
validated in CI to prevent breaking changes. Consumers should pin to `version == "health.v1"`.

## CI Integration

```yaml
- name: Readiness Smoke
  run: |
    rc health --readiness --json dist/health.json
```

Upload `dist/health.json` with the rest of the release artifacts so Historian can attach the
readiness verdict to each deployment.

## IAM Requirements

| Service | Actions | Scope |
| ------- | ------- | ----- |
| Secrets Manager | `secretsmanager:GetSecretValue` | Specific release secrets (e.g. `arn:aws:secretsmanager:REGION:ACCOUNT:secret:releasecopilot/*`) |
| DynamoDB | `DescribeTable`, `PutItem`, `DeleteItem` | ReleaseCopilot Jira cache table (e.g. `arn:aws:dynamodb:REGION:ACCOUNT:table/releasecopilot-jira-cache`) |
| S3 | `PutObject`, `DeleteObject` | Artifact bucket/prefix (e.g. `arn:aws:s3:::releasecopilot-artifacts/readiness/*`) |

## Troubleshooting

| Symptom | Likely Cause | Verification | Fix |
| ------- | ------------ | ------------ | --- |
| Secrets check fails | Missing IAM permission or incorrect ARN | Re-run with `--dry-run` and inspect `secrets` list. | Grant `secretsmanager:GetSecretValue` on the ARN or correct the value in `config/settings.yaml`. |
| DynamoDB check fails | Wrong table name or region mismatch | Run `aws dynamodb describe-table --table-name <name>` manually. | Update the table configuration or IAM policy. |
| S3 check fails | Missing write/delete permissions | Attempt `aws s3 cp` with the same prefix. | Grant `s3:PutObject` and `s3:DeleteObject` on the prefix. |
| Webhook secret empty | Environment variable unset or empty secret payload | Inspect `WEBHOOK_SECRET` / `WEBHOOK_SECRET_ARN` or fetch the secret in the console. | Set the environment variable or update the secret payload. |
| Cleanup warning present | Delete operation failed (S3 or DynamoDB) | Review CloudTrail events for the sentinel key/item. | Grant delete permissions or clean up manually. |

## Historian Anchors

- Store the readiness JSON alongside audit artifacts for traceability.
- Tag ledger entries with `health_schema=health.v1` to make future schema migrations explicit.

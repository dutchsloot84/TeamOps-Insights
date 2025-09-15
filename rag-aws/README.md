# TeamOps Insights — Jira Ingestion MVP

This repository contains a production-focused Retrieval-Augmented Generation (RAG) ingestion
pipeline that pulls Jira issues and stores both raw and normalized artifacts in Amazon S3. The
initial milestone is a Jira-only incremental sync that can be deployed quickly with Terraform and
extended later for chunking, indexing, and retrieval components.

## Architecture Overview

```
+---------------------+        rate(1 hour)         +--------------------+
|  EventBridge Rule   | --------------------------> |  Lambda Ingestor   |
+---------------------+                             +---------+----------+
                                                            |
                                                            v
                                                  +--------------------+
                                                  |        S3          |
                                                  |  raw / normalized  |
                                                  +--------------------+
                                                            |
                                                            v
                                            +----------------------------+
                                            |  SSM Parameter Store (cursor) |
                                            +----------------------------+
                                                            |
                                                            v
                                               +----------------------+
                                               |  Secrets Manager     |
                                               |  Jira OAuth secrets  |
                                               +----------------------+
```

The Lambda function runs on a schedule (default hourly) and performs the following tasks:

1. Fetches OAuth client credentials and refresh tokens from AWS Secrets Manager.
2. Retrieves the most recent synchronization cursor from AWS Systems Manager Parameter Store.
3. Calls Jira's REST API using OAuth 3LO to fetch updated issues, handling pagination, rate
   limits, and custom field discovery.
4. Persists the raw JSON payload for each issue to S3 under `raw/jira/<ISSUE KEY>/` and a normalized
   JSON document under `normalized/jira/<ISSUE KEY>.json`.
5. Updates the cursor in Parameter Store to the latest `updated` timestamp processed.

## Getting Started

You can run these commands from your local machine or from AWS CloudShell. The Terraform project is
self-contained and deploys everything required for the MVP ingestion pipeline.

### 1. Bootstrap Secrets Manager

Create a Secrets Manager secret named `rag/jira/oauth` (or any name you prefer) containing the Jira
OAuth refresh token bundle. The JSON structure must look like this:

```json
{
  "client_id": "YOUR-OAUTH-CLIENT-ID",
  "client_secret": "YOUR-OAUTH-CLIENT-SECRET",
  "refresh_token": "YOUR-REFRESH-TOKEN",
  "base_url": "https://yourtenant.atlassian.net"
}
```

### 2. Build the Lambda Artifact

```bash
make build
```

This command installs runtime dependencies, bundles the ingestion service, and creates
`services/ingest/jira_ingestor/jira_ingestor.zip` for Terraform to upload.

### 3. Deploy the Infrastructure

Run Terraform with your desired variables. The bucket name must be globally unique.

```bash
terraform -chdir=infra init
terraform -chdir=infra apply \
  -var="bucket_name=<unique-bucket-name>" \
  -var="jira_secret_arn=<arn-of-rag-jira-oauth>" \
  -var="region=us-west-2"
```

Alternatively, the Makefile includes wrappers (`make tf-init`, `make tf-plan`, `make tf-apply`).

### 4. Validate the Ingestor

Trigger the Lambda manually after deployment:

```bash
aws lambda invoke \
  --function-name rag-jira-ingestor \
  --cli-binary-format raw-in-base64-out \
  --payload '{}' \
  response.json
```

Inspect the response payload and CloudWatch Logs. You should find raw issue payloads beneath
`raw/jira/` and normalized outputs under `normalized/jira/` in the configured S3 bucket.

## Troubleshooting

- **401/403 Responses** – Re-authenticate in Jira and ensure the refresh token has `offline_access`,
  `read:jira-work`, and `read:jira-user` scopes. Confirm the secret JSON is correct and that the
  Lambda execution role can read it.
- **S3 or KMS Access Errors** – Make sure the Terraform deployment completed successfully and the
  Lambda role policies include S3 and KMS permissions for the managed key.
- **Cursor Not Advancing** – Check the CloudWatch Logs for warnings. The cursor is stored in
  Parameter Store at `/rag/jira/last_sync` by default. Deleting the parameter forces a 30-day
  backfill.
- **Rate Limits** – Jira may return HTTP 429. The ingestor automatically respects `Retry-After`
  headers and uses exponential backoff for other transient errors, but persistent failures will be
  logged with error-level context.

## Extending the System

This MVP intentionally isolates the ingestion responsibilities so future work can plug in additional
capabilities:

- **Chunking and Embedding** – Add a new Lambda or container task that processes normalized issue
  documents and writes embeddings to a vector database or index.
- **Retriever Service** – Publish an API Gateway/Lambda pair that orchestrates the RAG flow using the
  normalized store as ground truth.
- **Multi-Source Expansion** – Introduce additional ingestion services (Confluence, GitHub, etc.) by
  following the same packaging pattern and wiring them into the Terraform stack.

## Repository Layout

```
rag-aws/
├── Makefile
├── README.md
├── infra/
│   ├── main.tf
│   ├── outputs.tf
│   └── variables.tf
└── services/
    └── ingest/
        └── jira_ingestor/
            ├── adf_md.py
            ├── handler.py
            ├── jira_api.py
            ├── requirements.txt
            └── tests/
                ├── test_adf_md.py
                └── test_normalize.py
```

Each module is written with maintainability in mind and is covered by linting, typing, and unit
tests. Continuous integration via GitHub Actions keeps the quality gates active on every push and
pull request.

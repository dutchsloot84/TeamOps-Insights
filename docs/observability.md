# Observability and Resilience

ReleaseCopilot emits structured logs and automatically retries transient
network failures. This guide documents the core controls.

## Logging

Logs are emitted through a central configuration that writes to `stdout` using
ISO-8601 timestamps, module names, and the active correlation identifier.

### Log levels

* Default level is **INFO**. Use the `--log-level` CLI option or the
  `RC_LOG_LEVEL` environment variable to change verbosity.
* Levels follow the standard Python logging hierarchy:
  `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.

### JSON mode

Set `RC_LOG_JSON=true` to switch the formatter to JSON. Each record includes
`timestamp`, `level`, `logger`, `message`, and `correlation_id` plus any
structured context supplied via `logger.extra`.

### Correlation ID

Each process run is tagged with a correlation identifier (`RC_CORR_ID`) that is
included in every log line. A random UUID is generated when the variable is not
set. Propagate the correlation ID across worker processes to preserve request
traces.

### Secret redaction

Common secret tokens (e.g., values containing "token", "secret", "password",
"key", or "authorization") are automatically redacted to prevent accidental
exposure in logs.

All AWS Lambda entrypoints import the shared logging configuration during cold
starts. This ensures every function emits logs through the same filter chain
and inherits the redaction guarantees above without requiring per-function
customisation.

## Retry behaviour

Jira and Bitbucket HTTP calls are protected with exponential backoff and
jitter. Transient errors trigger up to five attempts when the response status
is `429` or any `5xx`, or when a timeout/connection error occurs.

* Backoff starts at one second and doubles on each attempt with random jitter.
* `Retry-After` headers are honoured—delays never fall below the server hint.
* Retry attempts are logged at the `WARNING` level with the request context
  (HTTP method, URL, repository/JQL details) and rate-limit headers.

### Disabling retries

Set `RC_DISABLE_RETRIES=true` to execute each request exactly once. This is
useful during debugging or when operating against mock services that do not
need retry protection.

## Jira cache idempotency

- Webhook ingestion stores every change under the composite DynamoDB key
  `issue_key` + `updated_at`. An `idempotency_key` derived from the webhook
  delivery identifier prevents duplicate sort keys when retries arrive.
- Delete events update the latest sort key in place and flag the record as a
  tombstone (`deleted=true`). Reconciliation performs the same mutation when it
  discovers missing issues so downstream consumers can filter deletes via the
  `deleted` attribute.
- Consumers such as `clients.jira_store.JiraIssueStore` query secondary indexes
  with `ScanIndexForward=False` and only emit the newest non-deleted version per
  `issue_key`. Historical versions remain available for audits and replay
  tooling.

# Jira Sync Webhook Lambda

This directory contains the source code for the Jira webhook ingestion Lambda. The
AWS CDK stack packages this folder directly using `Code.from_asset`, so the
folder **must remain committed to the repository** and accessible at
`services/jira_sync_webhook/` when `cdk synth` runs (both locally and in CI).

Any updates to the webhook handler should happen in place. If additional build
steps become necessary (for example, dependency bundling), ensure those steps
output to this directory or update the CDK asset path accordingly.

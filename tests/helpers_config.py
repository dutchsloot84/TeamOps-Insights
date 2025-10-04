from __future__ import annotations

from pathlib import Path
from typing import Mapping


class StubCredentialStore:
    """Test double for ``CredentialStore`` returning static payloads."""

    def __init__(self, payload: Mapping[str, Mapping[str, str]] | None = None) -> None:
        self.payload = payload or {}

    def get_all_from_secret(self, secret_id: str | None) -> Mapping[str, str]:
        if not secret_id:
            return {}
        return self.payload.get(secret_id, {})


DEFAULTS_TEMPLATE = """
aws:
  region: us-test-1
storage:
  dynamodb:
    jira_issue_table: table-default
  s3:
{bucket_block}    prefix: default-prefix
jira:
  base_url: https://defaults.example.com
  cloud_id: cloud-id
  scopes:
    project: DEMO
    fixVersion: "2024.01"
    jql: "project = DEMO"
  reconciliation:
    cron: cron(0 12 * * ? *)
    jql_template: ""
    fix_versions: ""
  credentials:
    client_id: null
    client_secret: null
    access_token: null
    refresh_token: null
    token_expiry: null
bitbucket:
  workspace: demo-workspace
  repositories: []
  default_branches:
    - main
  credentials:
    username: null
    app_password: null
    access_token: null
webhooks:
  jira:
    secret: null
secrets:
  jira_oauth:
    arn: arn:example:jira
    values:
      jira.credentials.client_id: client_id
  bitbucket_token:
    arn: arn:example:bitbucket
    values:
      bitbucket.credentials.username: username
  webhook_secret:
    arn: arn:example:webhook
    values:
      webhooks.jira.secret: secret
"""


def write_defaults(tmp_path: Path, *, missing_bucket: bool = False) -> Path:
    bucket_line = "    bucket: default-bucket\n" if not missing_bucket else ""
    content = DEFAULTS_TEMPLATE.format(bucket_block=bucket_line)
    defaults = tmp_path / "defaults.yml"
    defaults.write_text(content, encoding="utf-8")
    return defaults

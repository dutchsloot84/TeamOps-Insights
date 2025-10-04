from __future__ import annotations

from pathlib import Path

from src.config.loader import load_config

from tests.helpers_config import StubCredentialStore, write_defaults


def test_layered_config_precedence(tmp_path: Path) -> None:
    defaults_path = write_defaults(tmp_path)

    overrides_path = tmp_path / "overrides.yaml"
    overrides_path.write_text(
        """
storage:
  s3:
    bucket: file-bucket
    prefix: file-prefix
""",
        encoding="utf-8",
    )

    secrets = StubCredentialStore(
        {
            "arn:example:jira": {
                "client_id": "secret-client",
                "client_secret": "secret-secret",
            },
            "arn:example:webhook": {"secret": "webhook-secret"},
        }
    )

    env = {
        "JIRA_CLIENT_ID": "env-client",
        "JIRA_CLIENT_SECRET": "env-secret",
        "JIRA_BASE_URL": "https://env.example.com",
    }

    config = load_config(
        defaults_path=defaults_path,
        override_path=overrides_path,
        env=env,
        credential_store=secrets,
        overrides={"jira": {"credentials": {"client_id": "override-client"}}},
    )

    assert config["storage"]["s3"]["bucket"] == "file-bucket"
    assert config["storage"]["s3"]["prefix"] == "file-prefix"
    assert config["jira"]["base_url"] == "https://env.example.com"
    assert config["jira"]["credentials"]["client_id"] == "override-client"
    # Environment values should override secrets, but remain below explicit overrides
    assert config["jira"]["credentials"]["client_secret"] == "env-secret"
    assert config["webhooks"]["jira"]["secret"] == "webhook-secret"

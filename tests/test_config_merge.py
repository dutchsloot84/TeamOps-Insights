from __future__ import annotations

from pathlib import Path

from src.config.loader import load_config

from tests.helpers_config import StubCredentialStore, write_defaults


def test_override_file_applies_after_environment(tmp_path: Path) -> None:
    defaults = write_defaults(tmp_path)
    overrides_file = tmp_path / "settings.yaml"
    overrides_file.write_text(
        """
storage:
  s3:
    bucket: override-bucket
""",
        encoding="utf-8",
    )

    env = {"ARTIFACTS_BUCKET": "env-bucket"}
    config = load_config(
        defaults_path=defaults,
        override_path=overrides_file,
        env=env,
        credential_store=StubCredentialStore(),
    )

    assert config["storage"]["s3"]["bucket"] == "override-bucket"


def test_list_overrides_replace_values(tmp_path: Path) -> None:
    defaults = write_defaults(tmp_path)
    overrides = {"bitbucket": {"repositories": ["repo-1", "repo-2"]}}

    config = load_config(
        defaults_path=defaults,
        overrides=overrides,
        credential_store=StubCredentialStore(),
    )

    assert config["bitbucket"]["repositories"] == ["repo-1", "repo-2"]

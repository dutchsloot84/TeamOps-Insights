from src.config.loader import load_config


def test_config_loader_reads_required_keys(tmp_path):
    cfg = tmp_path / "settings.yaml"
    cfg.write_text(
        """
aws:
  region: us-west-2
jira:
  base_url: https://example.atlassian.net
bitbucket:
  workspace: demo
  repositories: []
""".strip(),
        encoding="utf-8",
    )

    config = load_config(cfg)
    assert config["aws"]["region"] == "us-west-2"
    assert config["bitbucket"]["repositories"] == []

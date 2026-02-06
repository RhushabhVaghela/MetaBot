from core.config import load_config


def test_load_config(temp_config_file):
    config = load_config(temp_config_file)
    assert config.system.name == "TestBot"
    assert config.adapters["openclaw"].port == 18789
    assert config.paths["external_repos"] == "/tmp/mock_repos"


def test_load_config_with_web_search(tmp_path):
    config_data = {
        "system": {
            "name": "Test",
            "local_only": True,
            "bind_address": "127.0.0.1",
            "telemetry": False,
            "default_mode": "plan",
        },
        "adapters": {
            "openclaw": {
                "web_search": {
                    "active_provider": "perplexity",
                    "providers": {"perplexity": {"api_key": "abc"}},
                }
            }
        },
        "paths": {"external_repos": "/tmp"},
    }
    config_file = tmp_path / "meta.yaml"
    import yaml

    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    config = load_config(str(config_file))
    assert config.adapters["openclaw"].web_search["active_provider"] == "perplexity"
    assert (
        config.adapters["openclaw"].web_search["providers"]["perplexity"]["api_key"]
        == "abc"
    )


def test_config_save(tmp_path):
    config_data = {
        "system": {
            "name": "Test",
            "local_only": True,
            "bind_address": "127.0.0.1",
            "telemetry": False,
            "default_mode": "plan",
        },
        "adapters": {"openclaw": {"host": "127.0.0.1", "port": 1234}},
        "paths": {"external_repos": "/tmp"},
        "policies": {"allow": ["pattern1"], "deny": ["pattern2"]},
    }
    config_file = tmp_path / "meta_save.yaml"
    from core.config import Config

    config = Config(**config_data)
    config.save(str(config_file))

    # Reload and verify
    reloaded = load_config(str(config_file))
    assert reloaded.policies["allow"] == ["pattern1"]
    assert reloaded.policies["deny"] == ["pattern2"]


def test_populate_from_environment(tmp_path, monkeypatch):
    """Test that environment variables are populated into config"""
    # Set environment variables
    monkeypatch.setenv("OPENAI_API_KEY", "test_openai_key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test_anthropic_key")
    monkeypatch.setenv("MEGABOT_BACKUP_KEY", "test_backup_key")

    config_data = {
        "system": {"name": "Test"},
        "adapters": {},
        "paths": {"workspaces": "/tmp", "external_repos": "/tmp"},
        "llm": {},
        "security": {},
    }
    config_file = tmp_path / "env_test.yaml"
    import yaml

    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    config = load_config(str(config_file))
    assert config.llm.openai_api_key == "test_openai_key"
    assert config.llm.anthropic_api_key == "test_anthropic_key"
    assert config.security.megabot_backup_key == "test_backup_key"


def test_load_api_credentials(tmp_path, monkeypatch):
    import os

    # Create a dummy api-credentials.py in tmp_path
    cred_file = tmp_path / "api-credentials.py"
    cred_file.write_text(
        "TEST_KEY = 'test-value'\nAUTHORIZED_ADMINS = ['user1', 'user2']\n"
    )

    # Change current working directory to tmp_path
    monkeypatch.chdir(tmp_path)

    from core.config import load_api_credentials

    load_api_credentials()

    assert os.environ.get("TEST_KEY") == "test-value"
    assert os.environ.get("AUTHORIZED_ADMINS") == "user1,user2"

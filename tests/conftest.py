import pytest
import yaml
import sys
import os
from unittest.mock import MagicMock
from core.config import Config, SystemConfig, AdapterConfig, SecurityConfig

# Set test environment variables before any imports
os.environ["MEGABOT_ENCRYPTION_SALT"] = "test-salt-minimum-16-chars"
os.environ["MEGABOT_BACKUP_KEY"] = "test-backup-key-32-chars-long-string"

# Global mocking for firebase_admin to prevent import errors in tests
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.messaging"] = MagicMock()
sys.modules["firebase_admin.app"] = MagicMock()
sys.modules["jwt"] = MagicMock()


@pytest.fixture(autouse=True)
def reset_orchestrator_global():
    """Reset orchestrator global state before/after each test"""
    import core.orchestrator as orch_module

    original = getattr(orch_module, "orchestrator", None)
    yield
    orch_module.orchestrator = original


@pytest.fixture
def mock_config():
    return Config(
        system=SystemConfig(
            name="TestBot",
            local_only=True,
            bind_address="127.0.0.1",
            telemetry=False,
            default_mode="plan",
        ),
        adapters={
            "openclaw": AdapterConfig(host="127.0.0.1", port=18789),
            "memu": AdapterConfig(
                database_url="sqlite:///:memory:", vector_db="sqlite"
            ),
            "mcp": AdapterConfig(servers=[]),
        },
        paths={"external_repos": "/tmp/mock_repos"},
        security=SecurityConfig(
            megabot_encryption_salt="test-salt-minimum-16-chars",
            megabot_backup_key="test-backup-key-32-chars-long-string",
        ),
    )


@pytest.fixture
def temp_config_file(tmp_path):
    config_data = {
        "system": {
            "name": "TestBot",
            "local_only": True,
            "bind_address": "127.0.0.1",
            "telemetry": False,
            "default_mode": "plan",
        },
        "adapters": {
            "openclaw": {"host": "127.0.0.1", "port": 18789},
            "memu": {"database_url": "sqlite:///:memory:", "vector_db": "sqlite"},
        },
        "paths": {"external_repos": "/tmp/mock_repos"},
        "llm_profiles": {},
        "security": {
            "megabot_encryption_salt": "test-salt-minimum-16-chars",
            "megabot_backup_key": "test-backup-key-32-chars-long-string",
        },
    }
    config_file = tmp_path / "test-config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
    return str(config_file)


@pytest.fixture
def orchestrator(mock_config):
    """Provide an Orchestrator instance for testing"""
    from core.orchestrator import MegaBotOrchestrator

    orch = MegaBotOrchestrator(mock_config)
    return orch

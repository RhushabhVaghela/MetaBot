"""Tests for projects and secrets modules"""

import pytest
import os
from unittest.mock import MagicMock, patch
from core.projects import ProjectManager
from core.secrets import SecretManager


class TestProjectManager:
    def test_project_init(self, tmp_path):
        pm = ProjectManager(str(tmp_path))
        assert pm.base_path == str(tmp_path)
        assert pm.current_project is None

    def test_create_project(self, tmp_path):
        pm = ProjectManager(str(tmp_path))
        ctx = pm.create_project("test_proj")
        assert ctx.name == "test_proj"
        assert os.path.exists(ctx.base_path)

    def test_switch_project(self, tmp_path):
        pm = ProjectManager(str(tmp_path))
        pm.switch_project("proj1")
        assert pm.current_project.name == "proj1"

    def test_delete_project(self, tmp_path):
        pm = ProjectManager(str(tmp_path))
        ctx = pm.create_project("proj_to_del")
        pm.delete_project("proj_to_del")
        assert not os.path.exists(ctx.base_path)


class TestSecretManager:
    def test_secret_init(self):
        sm = SecretManager()
        assert isinstance(sm.secrets, dict)

    def test_load_from_env(self, monkeypatch):
        monkeypatch.setenv("MEGABOT_SECRET_API_KEY", "secret-value")
        sm = SecretManager()
        assert sm.get_secret("API_KEY") == "secret-value"

    def test_inject_secrets(self):
        sm = SecretManager()
        sm.secrets["DB_PASS"] = "p4ssw0rd"
        text = "Connect with {{DB_PASS}}"
        assert sm.inject_secrets(text) == "Connect with p4ssw0rd"

    def test_scrub_secrets(self):
        sm = SecretManager()
        sm.secrets["TOKEN"] = "abc-123"
        text = "Your token is abc-123"
        assert sm.scrub_secrets(text) == "Your token is {{TOKEN}}"

import os
import tempfile
from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
async def test_write_file_dest_symlink(orchestrator, tmp_path):
    """If destination becomes a symlink before replace, write_file should deny."""
    from core.agent_coordinator import AgentCoordinator

    orch = orchestrator
    orch.config.paths["workspaces"] = str(tmp_path)
    coord = AgentCoordinator(orch)

    mock_agent = MagicMock()
    mock_agent.role = "tester"
    mock_agent._active = True
    mock_agent._get_sub_tools.return_value = [{"name": "write_file", "scope": "fs"}]
    orch.sub_agents = {"a1": mock_agent}

    orch.permissions = MagicMock()
    orch.permissions.is_authorized.return_value = True

    dest = tmp_path / "d.txt"
    # Ensure parent exists
    tmp_path.mkdir(parents=True, exist_ok=True)

    # Simulate post_stat reporting a symlink
    class FakeStat:
        st_mode = 0
        st_ino = 123
        st_dev = 1

    fake = FakeStat()

    orig_lstat = os.lstat
    orig_mkstemp = tempfile.mkstemp

    def fake_lstat(path):
        # Only spoof the destination path; delegate to original for other
        # paths. This avoids interfering with Path.resolve() internals.
        try:
            if str(path) == str(dest):
                return fake
            return orig_lstat(path)
        except Exception:
            # If original lstat fails, fall back to None to mimic missing file
            return None

    def fake_mkstemp(dir=None):
        # create a real tmp file and return fd, path
        fd, p = orig_mkstemp(dir=dir)
        return fd, p

    try:
        os.lstat = fake_lstat
        tempfile.mkstemp = fake_mkstemp
        res = await coord._execute_tool_for_sub_agent(
            "a1", {"name": "write_file", "input": {"path": str(dest), "content": "x"}}
        )
    finally:
        os.lstat = orig_lstat
        tempfile.mkstemp = orig_mkstemp

    assert "symlink" in res or "TOCTOU" in res


@pytest.mark.asyncio
async def test_write_file_success(orchestrator, tmp_path):
    """A normal write_file should succeed and return success message."""
    from core.agent_coordinator import AgentCoordinator

    orch = orchestrator
    orch.config.paths["workspaces"] = str(tmp_path)
    coord = AgentCoordinator(orch)

    mock_agent = MagicMock()
    mock_agent.role = "tester"
    mock_agent._active = True
    mock_agent._get_sub_tools.return_value = [{"name": "write_file", "scope": "fs"}]
    orch.sub_agents = {"a1": mock_agent}

    orch.permissions = MagicMock()
    orch.permissions.is_authorized.return_value = True

    dest = tmp_path / "ok.txt"
    res = await coord._execute_tool_for_sub_agent(
        "a1", {"name": "write_file", "input": {"path": str(dest), "content": "hello"}}
    )

    assert "written successfully" in res

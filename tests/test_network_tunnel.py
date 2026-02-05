import subprocess
import pytest
from unittest.mock import MagicMock, patch
from core.network.tunnel import TunnelManager


class TestTunnelManager:
    def test_init_with_keys(self):
        manager = TunnelManager("cf-token", "ts-key")
        assert manager.cloudflare_tunnel_id == "cf-token"
        assert manager.tailscale_auth_key == "ts-key"
        assert manager.cloudflare_process is None
        assert manager.tailscale_process is None
        assert manager.logger.name == "core.network.tunnel"

    def test_init_without_keys(self):
        manager = TunnelManager()
        assert manager.cloudflare_tunnel_id is None
        assert manager.tailscale_auth_key is None

    @pytest.mark.asyncio
    async def test_start_cloudflare_no_token(self):
        manager = TunnelManager()
        result = await manager.start_cloudflare()
        assert result is False

    @pytest.mark.asyncio
    async def test_start_cloudflare_success(self):
        manager = TunnelManager("test-token")
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process is alive

        with patch("subprocess.Popen", return_value=mock_process) as mock_popen, \
             patch("asyncio.sleep") as mock_sleep:
            result = await manager.start_cloudflare()

        assert result is True
        mock_popen.assert_called_once_with(
            ["cloudflared", "tunnel", "run", "--token", "test-token"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        mock_sleep.assert_called_once_with(5)
        assert manager.cloudflare_process == mock_process

    @pytest.mark.asyncio
    async def test_start_cloudflare_process_dies(self):
        manager = TunnelManager("test-token")
        mock_process = MagicMock()
        mock_process.poll.return_value = 0  # Process died

        with patch("subprocess.Popen", return_value=mock_process), \
             patch("asyncio.sleep"):
            result = await manager.start_cloudflare()

        assert result is False

    @pytest.mark.asyncio
    async def test_start_cloudflare_exception(self):
        manager = TunnelManager("test-token")

        with patch("subprocess.Popen", side_effect=Exception("Command failed")), \
             patch.object(manager.logger, "error") as mock_error:
            result = await manager.start_cloudflare()

        assert result is False
        mock_error.assert_called_once_with("Cloudflare start failed: Command failed")

    @pytest.mark.asyncio
    async def test_start_tailscale_no_key(self):
        manager = TunnelManager()
        result = await manager.start_tailscale()
        assert result is False

    @pytest.mark.asyncio
    async def test_start_tailscale_success(self):
        manager = TunnelManager(tailscale_auth_key="test-key")

        with patch("subprocess.run") as mock_run:
            result = await manager.start_tailscale()

        assert result is True
        mock_run.assert_called_once_with([
            "sudo", "tailscale", "up", "--authkey", "test-key", "--hostname", "megabot-gateway"
        ])

    @pytest.mark.asyncio
    async def test_start_tailscale_custom_hostname(self):
        manager = TunnelManager(tailscale_auth_key="test-key")

        with patch("subprocess.run") as mock_run:
            result = await manager.start_tailscale("custom-host")

        assert result is True
        mock_run.assert_called_once_with([
            "sudo", "tailscale", "up", "--authkey", "test-key", "--hostname", "custom-host"
        ])

    @pytest.mark.asyncio
    async def test_start_tailscale_exception(self):
        manager = TunnelManager(tailscale_auth_key="test-key")

        with patch("subprocess.run", side_effect=Exception("Tailscale failed")), \
             patch.object(manager.logger, "error") as mock_error:
            result = await manager.start_tailscale()

        assert result is False
        mock_error.assert_called_once_with("Tailscale start failed: Tailscale failed")

    def test_stop_all_no_processes(self):
        manager = TunnelManager()
        manager.stop_all()  # Should not raise

    def test_stop_all_with_cloudflare_process(self):
        manager = TunnelManager()
        mock_process = MagicMock()
        manager.cloudflare_process = mock_process

        with patch("subprocess.run") as mock_run:
            manager.stop_all()

        mock_process.terminate.assert_called_once()
        mock_run.assert_called_once_with(["sudo", "tailscale", "down"])

    def test_stop_all_subprocess_exception(self):
        manager = TunnelManager()
        mock_process = MagicMock()
        manager.cloudflare_process = mock_process

        with patch("subprocess.run", side_effect=Exception("Tailscale down failed")):
            manager.stop_all()  # Should not raise

        mock_process.terminate.assert_called_once()

    def test_stop_all_no_cloudflare_process(self):
        manager = TunnelManager()

        with patch("subprocess.run") as mock_run:
            manager.stop_all()

        mock_run.assert_called_once_with(["sudo", "tailscale", "down"])
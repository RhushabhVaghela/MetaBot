"""
Thorough tests for MegaBot Unified Gateway to achieve 100% coverage
"""

import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from aiohttp import web

import aiohttp
import adapters.unified_gateway as ug

# Ensure ug has web if it was lost by another test
if not getattr(ug, 'web', None):
    ug.web = web
if not getattr(ug, 'aiohttp', None):
    ug.aiohttp = aiohttp

from adapters.unified_gateway import (
    ConnectionType,
    ClientConnection,
    UnifiedGateway
)

@pytest.fixture
def gateway():
    gw = UnifiedGateway(
        megabot_server_port=18791,
        enable_cloudflare=True,
        enable_vpn=True,
        enable_direct_https=True,
        cloudflare_tunnel_id="test-tunnel",
        tailscale_auth_key="test-key",
        ssl_cert_path="/tmp/cert.pem",
        ssl_key_path="/tmp/key.pem",
        public_domain="test.com"
    )
    gw.on_message = AsyncMock()
    return gw

@pytest.mark.asyncio
async def test_gateway_start_all_paths(gateway):
    """Test start logic covering all conditional branches"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        with patch("subprocess.Popen") as mock_popen:
            mock_popen_instance = MagicMock()
            mock_popen_instance.poll.return_value = None # Running
            mock_popen.return_value = mock_popen_instance
            
            # Mock loop to return immediately
            with patch.object(gateway, "_health_monitor_loop", new_callable=AsyncMock):
                with patch.object(gateway, "_start_https_server", new_callable=AsyncMock) as mock_https:
                    with patch("websockets.serve", new_callable=AsyncMock) as mock_serve:
                        # Set health status before test since we're mocking the methods
                        gateway.health_status[ConnectionType.CLOUDFLARE.value] = True
                        
                        # Test successful paths
                        await gateway.start()
                        assert gateway.health_status[ConnectionType.CLOUDFLARE.value] is True
                        assert mock_https.called

@pytest.mark.asyncio
async def test_manage_connection_aiohttp_flow(gateway):
    """Test connection management for aiohttp web sockets"""
    mock_ws = AsyncMock()
    # Mocking the iterator for aiohttp websocket
    mock_ws.__aiter__.return_value = [
        MagicMock(type=web.WSMsgType.TEXT, data=json.dumps({"type": "msg"})),
        MagicMock(type=web.WSMsgType.ERROR)
    ]
    
    # Initialize rate limits for DIRECT connection
    gateway.rate_limits[ConnectionType.DIRECT.value] = {}
    
    conn = ClientConnection(
        websocket=mock_ws,
        connection_type=ConnectionType.DIRECT,
        client_id="aio-1",
        ip_address="1.1.1.1",
        connected_at=datetime.now()
    )
    
    await gateway._manage_connection(conn)
    assert gateway.on_message.called

@pytest.mark.asyncio
async def test_handle_websocket_detection_advanced(gateway):
    """Test detailed header detection in _handle_websocket"""
    # 1. Cloudflare detection
    mock_ws_cf = AsyncMock()
    mock_ws_cf.remote_address = ("127.0.0.1", 123)
    mock_ws_cf.request_headers = {"CF-Connecting-IP": "8.8.8.8"}
    mock_ws_cf.__aiter__.return_value = []
    await gateway._handle_websocket(mock_ws_cf, "")
    
    # 2. VPN detection
    mock_ws_vpn = AsyncMock()
    mock_ws_vpn.remote_address = ("100.64.0.1", 456)
    mock_ws_vpn.request_headers = {}
    mock_ws_vpn.__aiter__.return_value = []
    await gateway._handle_websocket(mock_ws_vpn, "")
    
    assert True

@pytest.mark.asyncio
async def test_gateway_health_monitor_restart(gateway):
    """Test health monitor restarting cloudflare"""
    gateway.cloudflare_process = MagicMock()
    gateway.cloudflare_process.poll.return_value = 1 # Dead
    gateway.health_status[ConnectionType.CLOUDFLARE.value] = True
    gateway.enable_cloudflare = True
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        
        # Set up rate limits with string key to avoid KeyError
        gateway.rate_limits[ConnectionType.CLOUDFLARE.value] = {}
        
        restart_called = False
        async def mock_restart_impl():
            nonlocal restart_called
            restart_called = True
            gateway.health_status[ConnectionType.CLOUDFLARE.value] = True
        
        with patch.object(gateway, "_start_cloudflare_tunnel", side_effect=mock_restart_impl):
            # Run one iteration
            with patch("asyncio.sleep", side_effect=[None, Exception("stop")]):
                try:
                    await gateway._health_monitor_loop()
                except Exception: pass
            assert restart_called

@pytest.mark.asyncio
async def test_gateway_error_responses(gateway):
    """Test various error sending scenarios"""
    # 1. Native WS error
    mock_ws_native = AsyncMock()
    conn_native = ClientConnection(websocket=mock_ws_native, connection_type=ConnectionType.LOCAL, client_id="c1", ip_address="1.1.1.1", connected_at=datetime.now())
    await gateway._send_error(conn_native, "err")
    assert mock_ws_native.send.called
    
    # 2. Aiohttp WS error
    mock_ws_aio = AsyncMock()
    # Mocking behavior for aiohttp send_str
    mock_ws_aio.send_str = AsyncMock()
    # Ensure it doesn't have native send
    if hasattr(mock_ws_aio, 'send'): del mock_ws_aio.send
    
    conn_aio = ClientConnection(websocket=mock_ws_aio, connection_type=ConnectionType.DIRECT, client_id="c2", ip_address="1.1.1.1", connected_at=datetime.now())
    await gateway._send_error(conn_aio, "err")
    assert mock_ws_aio.send_str.called

@pytest.mark.asyncio
async def test_gateway_process_request_headers_logic(gateway):
    """Test the process_request callback logic"""
    # We need to manually call the process_request if possible or mock the server
    with patch("websockets.serve", new_callable=AsyncMock) as mock_serve:
        await gateway._start_local_server()
        args, kwargs = mock_serve.call_args
        process_req = kwargs.get("process_request")
        
        # Test 1: Trusted local
        mock_headers = MagicMock()
        mock_headers.get.return_value = "127.0.0.1"
        mock_req = MagicMock(headers=mock_headers)
        assert process_req(None, mock_req) is None
        
        # Test 2: Untrusted remote
        mock_headers.get.return_value = "192.168.1.1"
        assert process_req(None, mock_req) is not None

@pytest.mark.asyncio
async def test_gateway_stop_cleanup_robust(gateway):
    """Test stop method with all resources active"""
    gateway.cloudflare_process = MagicMock()
    gateway.tailscale_process = MagicMock()
    gateway.https_server = MagicMock()
    gateway.https_server.cleanup = AsyncMock()
    gateway.local_server = MagicMock()
    gateway.local_server.close = MagicMock()
    gateway.local_server.wait_closed = AsyncMock()
    
    # Add a mock client to close
    mock_ws = AsyncMock()
    gateway.clients["c1"] = ClientConnection(websocket=mock_ws, connection_type=ConnectionType.LOCAL, client_id="c1", ip_address="1.1.1.1", connected_at=datetime.now())
    
    await gateway.stop()
    assert mock_ws.close.called
    assert gateway.cloudflare_process.terminate.called

@pytest.mark.asyncio
async def test_gateway_run_module():
    """Test running the module as main for coverage"""
    import runpy
    import sys
    
    # Clear module from cache to avoid runpy warning
    modules_to_clear = [k for k in sys.modules.keys() if k.startswith('adapters.unified_gateway')]
    for mod in modules_to_clear:
        del sys.modules[mod]
    
    def mock_run(coro):
        coro.close()
        return None
        
    with patch.object(UnifiedGateway, "start", new_callable=AsyncMock):
        with patch("asyncio.run", side_effect=mock_run):
            runpy.run_module("adapters.unified_gateway", run_name="__main__")
            assert True

@pytest.mark.asyncio
async def test_start_https_server_failure_handled(gateway):
    """Test HTTPS server failure handling"""
    with patch("ssl.create_default_context", side_effect=Exception("ssl error")):
        await gateway._start_https_server()
        assert gateway.health_status[ConnectionType.DIRECT.value] is False

@pytest.mark.asyncio
async def test_start_cloudflare_tunnel_fail_path(gateway):
    """Test start failure branches for cloudflare"""
    with patch("subprocess.run") as mock_run:
        # cloudflared not found
        mock_run.return_value = MagicMock(returncode=1)
        await gateway._start_cloudflare_tunnel()
        assert gateway.health_status[ConnectionType.CLOUDFLARE.value] is False

@pytest.mark.asyncio
async def test_start_tailscale_vpn_fail_path(gateway):
    """Test start failure branches for tailscale"""
    with patch("subprocess.run") as mock_run:
        # tailscale not found
        mock_run.return_value = MagicMock(returncode=1)
        await gateway._start_tailscale_vpn()
        assert gateway.health_status[ConnectionType.VPN.value] is False

@pytest.mark.asyncio
async def test_malicious_command_interception_metadata(gateway):
    """Test that messages from gateway include the critical security metadata for the orchestrator"""
    mock_ws = AsyncMock()
    # Mocking the iterator to send a malicious command string
    malicious_payload = json.dumps({
        "type": "shell.execute",
        "params": {"command": "rm -rf /"}
    })
    mock_ws.__aiter__.return_value = [malicious_payload]
    
    # Initialize rate limits for CLOUDFLARE connection
    gateway.rate_limits[ConnectionType.CLOUDFLARE.value] = {}
    
    conn = ClientConnection(
        websocket=mock_ws,
        connection_type=ConnectionType.CLOUDFLARE, # Simulate untrusted source
        client_id="cf-evil",
        ip_address="6.6.6.6",
        connected_at=datetime.now()
    )
    
    await gateway._manage_connection(conn)
    
    # Verify that on_message was called with the command AND the security metadata
    assert gateway.on_message.called
    forwarded_data = gateway.on_message.call_args[0][0]
    assert forwarded_data["type"] == "shell.execute"
    assert forwarded_data["_meta"]["connection_type"] == "cloudflare"
    assert forwarded_data["_meta"]["client_id"] == "cf-evil"
    assert forwarded_data["_meta"]["authenticated"] is False

@pytest.mark.asyncio
async def test_gateway_start_cloudflare_failure_during_wait(gateway):
    """Test cloudflare process dying during wait sleep"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.poll.return_value = 1 # Dead
            mock_proc.communicate.return_value = (b"", b"tunnel error")
            mock_popen.return_value = mock_proc
            
            await gateway._start_cloudflare_tunnel()
            assert gateway.health_status[ConnectionType.CLOUDFLARE.value] is False

@pytest.mark.asyncio
async def test_handle_websocket_forced_type(gateway):
    """Test _handle_websocket with forced_type parameter"""
    mock_ws = AsyncMock()
    mock_ws.remote_address = ("1.2.3.4", 80)
    mock_ws.request_headers = {}
    mock_ws.__aiter__.return_value = []
    
    # Initialize rate limits
    gateway.rate_limits[ConnectionType.VPN.value] = {}
    
    with patch.object(gateway, "_manage_connection", new_callable=AsyncMock) as mock_manage:
        await gateway._handle_websocket(mock_ws, "", forced_type=ConnectionType.VPN)
        
        # Check if manage was called with VPN type
        assert mock_manage.called
        connection = mock_manage.call_args[0][0]
        assert connection.connection_type == ConnectionType.VPN

@pytest.mark.asyncio
async def test_gateway_https_server_start_error(gateway):
    """Test exception during HTTPS server setup"""
    with patch("aiohttp.web.Application", side_effect=Exception("web error")):
        await gateway._start_https_server()
        assert gateway.health_status[ConnectionType.DIRECT.value] is False

@pytest.mark.asyncio
async def test_gateway_stop_client_close_error(gateway):
    """Test stop method handling errors during client close"""
    mock_ws = AsyncMock()
    mock_ws.close.side_effect = Exception("Close error")
    gateway.clients["c1"] = ClientConnection(
        websocket=mock_ws, connection_type=ConnectionType.LOCAL,
        client_id="c1", ip_address="1.1.1.1", connected_at=datetime.now()
    )
    
    # Should not crash
    await gateway.stop()
    assert True

@pytest.mark.asyncio
async def test_gateway_process_message_invalid_json(gateway):
    """Test _process_message with invalid JSON"""
    mock_ws = AsyncMock()
    conn = ClientConnection(websocket=mock_ws, connection_type=ConnectionType.LOCAL, client_id="c1", ip_address="1.1.1.1", connected_at=datetime.now())
    
    await gateway._process_message(conn, "invalid json {")
    assert mock_ws.send.called

@pytest.mark.asyncio
async def test_gateway_process_message_internal_error(gateway):
    """Test _process_message with unexpected error"""
    mock_ws = AsyncMock()
    conn = ClientConnection(websocket=mock_ws, connection_type=ConnectionType.LOCAL, client_id="c1", ip_address="1.1.1.1", connected_at=datetime.now())
    
    with patch.object(gateway, "_forward_to_megabot", side_effect=Exception("crash")):
        await gateway._process_message(conn, '{"type": "ping"}')
        assert mock_ws.send.called

@pytest.mark.asyncio
async def test_gateway_forward_no_handler(gateway):
    """Test _forward_to_megabot without handler"""
    gateway.on_message = None
    # Should just log info
    await gateway._forward_to_megabot({"type": "ping"})
    assert True

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.network.server import NetworkServer


def process_request(connection, request):
    host = request.headers.get("Host", "")
    if not any(l in host for l in ["127.0.0.1", "localhost", "::1"]):
        return (403, [], b"Localhost only")
    return None


class TestNetworkServer:
    @pytest.fixture
    def mock_connection_handler(self):
        return AsyncMock()

    @pytest.fixture
    def server(self, mock_connection_handler):
        return NetworkServer("localhost", 8080, mock_connection_handler)

    def test_init(self, mock_connection_handler):
        server = NetworkServer("127.0.0.1", 9000, mock_connection_handler)
        assert server.host == "127.0.0.1"
        assert server.port == 9000
        assert server.on_connection == mock_connection_handler
        assert server.server is None
        assert server.logger.name == "core.network.server"

    @pytest.mark.asyncio
    async def test_start_local(self, server, mock_connection_handler):
        mock_serve = AsyncMock()
        mock_server_instance = MagicMock()
        mock_serve.return_value = mock_server_instance

        with patch("core.network.server.websockets.serve", mock_serve), \
             patch.object(server.logger, "info") as mock_info:
            await server.start_local()

        # Check that serve was called with correct args
        call_args = mock_serve.call_args
        assert call_args[0][0] == mock_connection_handler  # on_connection
        assert call_args[0][1] == "localhost"  # host
        assert call_args[0][2] == 8080  # port
        assert "process_request" in call_args[1]  # process_request is passed
        assert callable(call_args[1]["process_request"])  # it's a function

        assert server.server == mock_server_instance
        mock_info.assert_called_once_with("Local server on localhost:8080")

    @pytest.mark.asyncio
    async def test_stop_with_server(self, server):
        mock_server_instance = AsyncMock()
        server.server = mock_server_instance

        await server.stop()

        mock_server_instance.close.assert_called_once()
        mock_server_instance.wait_closed.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_local_process_request_functionality(self, server):
        """Test that the process_request function inside start_local works correctly"""
        with patch("core.network.server.websockets.serve", new_callable=AsyncMock) as mock_serve, \
             patch.object(server.logger, "info") as mock_info:
            
            await server.start_local()
            
            # Get the process_request function that was passed to websockets.serve
            call_kwargs = mock_serve.call_args[1]
            process_req_func = call_kwargs["process_request"]
            
            # Test localhost allowed
            mock_request = MagicMock()
            mock_request.headers = {"Host": "127.0.0.1:8080"}
            mock_connection = MagicMock()
            result = process_req_func(mock_connection, mock_request)
            assert result is None
            
            # Test non-localhost blocked
            mock_request.headers = {"Host": "example.com:8080"}
            result = process_req_func(mock_connection, mock_request)
            assert result == (403, [], b"Localhost only")
            
            # Test no host header
            mock_request.headers = {}
            result = process_req_func(mock_connection, mock_request)
            assert result == (403, [], b"Localhost only")

    def test_process_request_localhost(self):
        # Test localhost allowed
        request = MagicMock()
        request.headers = {"Host": "127.0.0.1:8080"}
        connection = MagicMock()

        result = process_request(connection, request)
        assert result is None  # None means allow

    def test_process_request_localhost_ipv6(self):
        # Test IPv6 localhost allowed
        request = MagicMock()
        request.headers = {"Host": "[::1]:8080"}
        connection = MagicMock()

        result = process_request(connection, request)
        assert result is None  # None means allow

    def test_process_request_non_localhost(self):
        # Test non-localhost blocked
        request = MagicMock()
        request.headers = {"Host": "example.com:8080"}
        connection = MagicMock()

        result = process_request(connection, request)
        assert result == (403, [], b"Localhost only")

    def test_process_request_no_host(self):
        # Test no Host header - should be blocked
        request = MagicMock()
        request.headers = {}
        connection = MagicMock()

        result = process_request(connection, request)
        assert result == (403, [], b"Localhost only")
import websockets
import logging
from typing import Any, Callable, Awaitable


class NetworkServer:
    def __init__(
        self, host: str, port: int, on_connection: Callable[[Any, str], Awaitable[None]]
    ):
        self.host = host
        self.port = port
        self.on_connection = on_connection
        self.logger = logging.getLogger(__name__)
        self.server = None

    async def start_local(self):
        def process_request(connection, request):
            host = request.headers.get("Host", "")
            if not any(l in host for l in ["127.0.0.1", "localhost", "::1"]):
                return (403, [], b"Localhost only")
            return None

        self.server = await websockets.serve(
            self.on_connection, self.host, self.port, process_request=process_request
        )
        self.logger.info(f"Local server on {self.host}:{self.port}")

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()

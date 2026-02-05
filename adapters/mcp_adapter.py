import asyncio
import json
import subprocess
from typing import Any, List, Dict, Optional
from core.interfaces import ToolInterface


class MCPAdapter(ToolInterface):
    def __init__(self, server_config: Dict[str, Any]):
        self.name = server_config["name"]
        self.command = server_config["command"]
        self.args = server_config.get("args", [])
        self.process = None
        self.tools: List[Dict[str, Any]] = []

    async def start(self):
        self.process = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        print(f"Started MCP Server: {self.name}")
        # Fetch tool list on startup
        try:
            res = await self.execute(method="tools/list")
            if res and "result" in res:
                self.tools = res["result"].get("tools", [])
                print(f"Server '{self.name}' provided {len(self.tools)} tools.")
        except Exception as e:
            print(f"Failed to fetch tools for {self.name}: {e}")

    async def execute(self, **kwargs) -> Any:
        method = kwargs.get("method")
        params = kwargs.get("params", {})
        if not self.process:
            await self.start()

        request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}

        if self.process and self.process.stdin:
            self.process.stdin.write(json.dumps(request).encode() + b"\n")
            await self.process.stdin.drain()

            if self.process.stdout:
                line = await self.process.stdout.readline()
                if line:
                    return json.loads(line.decode())
        return None


class MCPManager:
    def __init__(self, configs: List[Dict[str, Any]]):
        self.servers = {cfg["name"]: MCPAdapter(cfg) for cfg in configs}

    async def start_all(self):
        for server in self.servers.values():
            await server.start()

    def find_server_for_tool(self, tool_name: str) -> Optional[str]:
        """Find which MCP server provides the specified tool"""
        for server_name, adapter in self.servers.items():
            if any(t["name"] == tool_name for t in adapter.tools):
                return server_name
        return None

    async def call_tool(
        self, server_name: Optional[str], tool_name: str, params: Dict[str, Any]
    ):
        if not server_name:
            server_name = self.find_server_for_tool(tool_name)

        if not server_name:
            # Fallback to first server if only one is available
            if len(self.servers) == 1:
                server_name = list(self.servers.keys())[0]
            else:
                return {"error": f"Tool '{tool_name}' not found on any MCP server."}

        server = self.servers.get(server_name)
        if server:
            return await server.execute(
                method="tools/call", params={"name": tool_name, "arguments": params}
            )
        return {"error": f"Server '{server_name}' not found."}

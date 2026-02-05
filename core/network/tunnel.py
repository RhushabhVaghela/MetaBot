import subprocess
import logging
import asyncio
from typing import Optional


class TunnelManager:
    def __init__(
        self,
        cloudflare_tunnel_id: Optional[str] = None,
        tailscale_auth_key: Optional[str] = None,
    ):
        self.cloudflare_tunnel_id = cloudflare_tunnel_id
        self.tailscale_auth_key = tailscale_auth_key
        self.cloudflare_process: Optional[subprocess.Popen] = None
        self.tailscale_process: Optional[subprocess.Popen] = None
        self.logger = logging.getLogger(__name__)

    async def start_cloudflare(self) -> bool:
        if not self.cloudflare_tunnel_id:
            return False
        try:
            cmd = [
                "cloudflared",
                "tunnel",
                "run",
                "--token",
                str(self.cloudflare_tunnel_id),
            ]
            self.cloudflare_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            await asyncio.sleep(5)
            return self.cloudflare_process.poll() is None
        except Exception as e:
            self.logger.error(f"Cloudflare start failed: {e}")
            return False

    async def start_tailscale(self, hostname: str = "megabot-gateway") -> bool:
        if not self.tailscale_auth_key:
            return False
        try:
            subprocess.run(
                [
                    "sudo",
                    "tailscale",
                    "up",
                    "--authkey",
                    self.tailscale_auth_key,
                    "--hostname",
                    hostname,
                ]
            )
            return True
        except Exception as e:
            self.logger.error(f"Tailscale start failed: {e}")
            return False

    def stop_all(self):
        if self.cloudflare_process:
            self.cloudflare_process.terminate()
        try:
            subprocess.run(["sudo", "tailscale", "down"])
        except Exception:
            pass

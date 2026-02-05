import sys
sys.path.insert(0, '.')
import asyncio

async def run_test():
    from core.network.gateway import UnifiedGateway, ConnectionType
    gateway = UnifiedGateway(
        megabot_server_host='custom-host',
        megabot_server_port=9999,
        enable_cloudflare=True,
        enable_vpn=True,
        enable_direct_https=True,
        cloudflare_tunnel_id='tunnel-123',
        tailscale_auth_key='auth-key-123',
        ssl_cert_path='/path/to/cert.crt',
        ssl_key_path='/path/to/key.key',
        public_domain='example.com',
        on_message=lambda x: None,
    )

    assert gateway.megabot_host == 'custom-host'
    assert gateway.megabot_port == 9999
    assert gateway.enable_cloudflare is True
    assert gateway.enable_vpn is True
    assert gateway.enable_direct_https is True
    assert gateway.cloudflare_tunnel_id == 'tunnel-123'
    assert gateway.tailscale_auth_key == 'auth-key-123'
    assert gateway.ssl_cert_path == '/path/to/cert.crt'
    assert gateway.ssl_key_path == '/path/to/key.key'
    assert gateway.public_domain == 'example.com'
    assert gateway.on_message is not None
    assert gateway.clients == {}
    assert gateway.health_status[ConnectionType.LOCAL.value] is True
    assert gateway.health_status[ConnectionType.CLOUDFLARE.value] is False
    assert gateway.health_status[ConnectionType.VPN.value] is False
    assert gateway.health_status[ConnectionType.DIRECT.value] is False
    print('Test passed')

if __name__ == "__main__":
    asyncio.run(run_test())
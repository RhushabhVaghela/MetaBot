The Unified Gateway provides multiple secure access methods to your MegaBot instance, now modularized under `core/network/` for clarity and testability.

## Overview
- `core/network/gateway.py`: `UnifiedGateway` orchestrates connection selection, rate limiting (default 1000/min), health checks, and start/stop lifecycle.
- `monitor.py`: Health monitor loop; surfaces health and active endpoints.
- `server.py`: Local websocket server for direct/local traffic.
- `tunnel.py`: Tunnel helpers (Cloudflare / Tailscale).
- Connection types (`ConnectionType`): `cloudflare`, `vpn`, `direct`, `local`.
- Fallback: auto-detect available connection types; fallback based on availability/health. `get_connection_info()` reports health and endpoints.

## Setup & Usage
- Instantiate `UnifiedGateway` and call `start()` to bootstrap transports (Cloudflare tunnel, Tailscale VPN, optional HTTPS via `aiohttp`, local websocket). Call `stop()` for clean teardown.
- Local websocket runs from `server.py`; HTTPS handler uses `aiohttp` when enabled.

## Configuration Flags
- `enable_cloudflare`
- `cloudflare_tunnel_id`
- `enable_vpn`
- `tailscale_auth_key`
- `enable_direct_https`

## Connection Types & Fallback
- Types: `cloudflare`, `vpn`, `direct`, `local`.
- Local websocket is the final fallback.

## Health Monitoring
- Background health loop monitors Cloudflare/Tailscale/Direct/Local and updates `get_connection_info()`.

## Rate Limiting
- Default: 1000 requests/minute (global limiter in `UnifiedGateway`).

## Testing
```bash
PYTHONPATH=. pytest tests/test_unified_gateway.py
```
(recent runs: passes; also validated together with messaging tests.)

## Notes
- Shim: `adapters/unified_gateway.py` re-exports `UnifiedGateway`, `ConnectionType`, `ClientConnection`, `HealthMonitor`, `TunnelManager`, and `datetime` (tests patch `adapters.unified_gateway.datetime`).
- Keep docs ASCII and concise.

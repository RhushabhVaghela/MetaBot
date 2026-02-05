## refactor: finalize unified gateway and messaging imports
- Added `core/network/` gateway stack (gateway, monitor, server, tunnel) with connection detection, health monitoring, rate limiting, and fallback across Cloudflare, VPN, direct HTTPS, and local websocket.
- Introduced `adapters/unified_gateway.py` shim re-exporting gateway classes and `datetime` for test patching.
- Messaging now enters via `adapters/messaging/__main__.py`; orchestrator imports `PlatformMessage`/`MessageType` from `adapters.messaging`; removed legacy `megabot_messaging` monolith references.
- Tests updated: `PYTHONPATH=. pytest tests/test_unified_gateway.py tests/test_megabot_messaging.py` (passing).

adapters/unified_gateway Shim
=============================

Purpose
-------
- Compatibility shim that bridges previous imports to the new `core.network.gateway` implementation.

Re-exports
----------
- `UnifiedGateway`
- `ConnectionType`
- `ClientConnection`
- `HealthMonitor`
- `TunnelManager`
- `datetime` (tests patch `adapters.unified_gateway.datetime`)

Testing Note
------------
- Tests patch `adapters.unified_gateway.datetime`; retain the re-export to keep tests stable.

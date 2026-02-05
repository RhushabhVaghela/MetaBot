Messaging Entrypoint & Imports
==============================

Entrypoint
----------
- Run via `adapters/messaging/__main__.py` (CLI entry).
- `main` is defined in `adapters/messaging/__init__.py` and imported by the entrypoint.
- Tests invoke `adapters/messaging/__main__.py` argv.

Orchestrator Imports
--------------------
- Orchestrator imports `PlatformMessage` and `MessageType` from `adapters.messaging`.

Removal
-------
- Legacy `megabot_messaging` monolith removed; use `adapters/messaging` entrypoint instead.

Testing
-------
```bash
PYTHONPATH=. pytest tests/test_megabot_messaging.py
```
(part of the validated 204 passing tests when run with unified gateway tests.)

Orchestrator Components
======================

BackgroundTasks
- Responsible for periodic maintenance loops: `sync_loop`, `proactive_loop`, `pruning_loop`, `backup_loop`.
- Defensive scheduling: `start_all_tasks` attempts to schedule each loop with `asyncio.create_task`, falling back to `asyncio.ensure_future`. If scheduling functions are patched or fail, `start_all_tasks` ensures coroutines are closed to avoid "coroutine was never awaited" warnings.
- Tasks are tracked in `self._tasks` for clean shutdown.

HealthMonitor
- Periodically collects health data from adapters and maintains `last_status` and `restart_counts`.
- Start/stop logic is defensive and stores the task in the orchestrator's background tasks store so shutdown cancels it safely.

MessageHandler
- Routes / processes incoming messages, handles admin commands, attachments, and mode-specific behavior.

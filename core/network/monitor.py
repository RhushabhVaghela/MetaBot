from datetime import datetime
from typing import Dict, List


class HealthMonitor:
    def __init__(self):
        self.status: Dict[str, bool] = {}

    def update(self, key: str, is_healthy: bool):
        self.status[key] = is_healthy


class RateLimiter:
    def __init__(self):
        self.history: Dict[str, List[datetime]] = {}

    def check(self, client_id: str, limit: int = 100, window: int = 60) -> bool:
        now = datetime.now()
        if client_id not in self.history:
            self.history[client_id] = []
        self.history[client_id] = [
            t for t in self.history[client_id] if (now - t).total_seconds() < window
        ]
        if len(self.history[client_id]) >= limit:
            return False
        self.history[client_id].append(now)
        return True

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
from core.network.monitor import HealthMonitor, RateLimiter


class TestHealthMonitor:
    def test_init(self):
        monitor = HealthMonitor()
        assert monitor.status == {}

    def test_update(self):
        monitor = HealthMonitor()
        monitor.update("gateway", True)
        assert monitor.status["gateway"] is True

        monitor.update("server", False)
        assert monitor.status["server"] is False
        assert monitor.status["gateway"] is True

    def test_update_multiple(self):
        monitor = HealthMonitor()
        monitor.update("service1", True)
        monitor.update("service1", False)  # Update same key
        assert monitor.status["service1"] is False

    @pytest.mark.asyncio
    async def test_stop(self):
        """Test health monitor stop"""
        monitor = HealthMonitor()
        assert monitor._running is True
        await monitor.stop()
        assert monitor._running is False


class TestRateLimiter:
    def test_init(self):
        limiter = RateLimiter()
        assert limiter.history == {}

    def test_check_first_request(self):
        limiter = RateLimiter()
        result = limiter.check("client1")
        assert result is True
        assert "client1" in limiter.history
        assert len(limiter.history["client1"]) == 1

    def test_check_under_limit(self):
        limiter = RateLimiter()
        for i in range(50):
            assert limiter.check("client1", limit=100) is True
        assert len(limiter.history["client1"]) == 50

    def test_check_at_limit(self):
        limiter = RateLimiter()
        for i in range(100):
            limiter.check("client1", limit=100)
        assert limiter.check("client1", limit=100) is False  # Should be at limit

    def test_check_over_limit(self):
        limiter = RateLimiter()
        for i in range(101):
            result = limiter.check("client1", limit=100)
            if i < 100:
                assert result is True
            else:
                assert result is False

    @patch("core.network.monitor.datetime")
    def test_check_window_cleanup(self, mock_datetime):
        # Test that old requests are cleaned up
        limiter = RateLimiter()
        base_time = datetime(2023, 1, 1, 12, 0, 0)

        # Simulate requests over time
        times = [
            base_time,  # First request
            base_time + timedelta(seconds=30),  # Second request
            base_time + timedelta(seconds=70),  # Third request (after window)
        ]

        for i, t in enumerate(times):
            mock_datetime.now.return_value = t
            result = limiter.check("client1", limit=2, window=60)
            if i < 2:
                assert result is True
            else:
                # First request should be cleaned up (70-0=70 > 60), so only 1 in window
                assert result is True

        # Check that only recent requests are kept
        assert len(limiter.history["client1"]) == 2  # Should have last 2 requests

    def test_check_different_clients(self):
        limiter = RateLimiter()
        assert limiter.check("client1", limit=5) is True
        assert limiter.check("client2", limit=5) is True
        assert limiter.check("client1", limit=5) is True  # client1 second request

        # client1 should have 2, client2 should have 1
        assert len(limiter.history["client1"]) == 2
        assert len(limiter.history["client2"]) == 1

    def test_check_custom_limits(self):
        limiter = RateLimiter()
        # Test with limit=1
        assert limiter.check("client1", limit=1) is True
        assert limiter.check("client1", limit=1) is False

    def test_check_custom_window(self):
        limiter = RateLimiter()
        limiter.check("client1", limit=1, window=30)  # Should work with custom window

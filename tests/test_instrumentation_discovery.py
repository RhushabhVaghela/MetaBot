"""Tests for ModuleDiscovery and Instrumentation"""

import pytest
import os
from unittest.mock import MagicMock, patch
from core.discovery import ModuleDiscovery
from core.instrumentation import track_telemetry


class TestModuleDiscovery:
    def test_discovery_init(self):
        discovery = ModuleDiscovery("/tmp")
        assert discovery.base_path == "/tmp"
        assert discovery.capabilities == {}

    def test_scan_modules(self):
        discovery = ModuleDiscovery("/tmp")
        with patch("os.path.exists", return_value=True):
            with patch("os.listdir", return_value=["skill1", "skill2"]):
                with patch("os.path.isdir", return_value=True):
                    discovery.scan()
                    assert "skill1" in discovery.capabilities
                    assert "skill2" in discovery.capabilities

    def test_get_capability_path(self):
        discovery = ModuleDiscovery("/tmp")
        discovery.capabilities["test"] = "/tmp/test"
        assert discovery.get_capability_path("test") == "/tmp/test"
        assert discovery.get_capability_path("unknown") is None


class TestInstrumentation:
    @pytest.mark.asyncio
    async def test_track_telemetry_success(self):
        """Test track_telemetry decorator success path"""

        class MockProvider:
            model = "test-model"

            @track_telemetry
            async def generate(self, prompt):
                return {"choices": [{"text": "hello"}], "usage": {"total_tokens": 10}}

        provider = MockProvider()
        with patch("core.instrumentation.logger") as mock_logger:
            result = await provider.generate("hi")
            assert result["usage"]["total_tokens"] == 10
            assert mock_logger.info.called

    @pytest.mark.asyncio
    async def test_track_telemetry_error(self):
        """Test track_telemetry decorator error path"""

        class MockProvider:
            model = "test-model"

            @track_telemetry
            async def generate(self, prompt):
                raise Exception("API Error")

        provider = MockProvider()
        with patch("core.instrumentation.logger") as mock_logger:
            with pytest.raises(Exception, match="API Error"):
                await provider.generate("hi")
            assert mock_logger.error.called

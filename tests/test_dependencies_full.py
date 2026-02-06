"""Tests for dependency injection system"""

import pytest
from core.dependencies import (
    DependencyContainer,
    register_service,
    resolve_service,
    dependency_scope,
    inject,
)


class MockService:
    def __init__(self, value="default"):
        self.value = value


class TestDependencyInjection:
    def test_container_register_resolve(self):
        container = DependencyContainer()
        service = MockService("test")
        container.register(MockService, service)

        resolved = container.resolve(MockService)
        assert resolved is service
        assert resolved.value == "test"

    def test_container_factory(self):
        container = DependencyContainer()
        container.register_factory(MockService, lambda: MockService("factory"))

        resolved = container.resolve(MockService)
        assert resolved.value == "factory"

    def test_container_singleton(self):
        container = DependencyContainer()
        service = MockService("singleton")
        container.register_singleton(MockService, service)

        resolved1 = container.resolve(MockService)
        resolved2 = container.resolve(MockService)
        assert resolved1 is resolved2 is service

    def test_dependency_scope(self):
        register_service(MockService, MockService("global"))
        assert resolve_service(MockService).value == "global"

        with dependency_scope() as scoped_container:
            scoped_container.register(MockService, MockService("scoped"))
            assert resolve_service(MockService).value == "scoped"

        assert resolve_service(MockService).value == "global"

    def test_inject_decorator_class(self):
        with dependency_scope() as container:
            service = MockService("injected")
            container.register(MockService, service)

            @inject(MockService)
            class Client:
                # Type annotation is used for injection
                service: MockService

                def __init__(self, service: MockService = None):
                    self.service = service

            client = Client()
            assert client.service is service
            assert client.service.value == "injected"

    def test_inject_decorator_function(self):
        with dependency_scope() as container:
            service = MockService("func_injected")
            container.register(MockService, service)

            # Annotation must be present before decorator is applied
            def base_function(service: MockService = None):
                return service

            # Verify annotation exists
            assert "service" in base_function.__annotations__

            injected_func = inject(MockService)(base_function)

            result = injected_func()
            assert result is service
            assert result.value == "func_injected"

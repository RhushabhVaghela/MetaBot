# Platform adapters for MegaBot
"""
Adapters for integrating MegaBot with various messaging platforms and external services.
"""

from .unified_gateway import UnifiedGateway, ConnectionType, ClientConnection
from .messaging import MegaBotMessagingServer, PlatformMessage, MessageType

__all__ = [
    "UnifiedGateway",
    "ConnectionType",
    "ClientConnection",
    "MegaBotMessagingServer",
    "PlatformMessage",
    "MessageType",
]

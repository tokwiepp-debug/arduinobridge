"""
ArduinoBridge Core
Cross-platform Arduino programming assistant
"""

__version__ = "0.1.0"

from .port_scanner import list_ports, filter_arduino_ports
from .board_identifier import identify_board, BoardInfo
from .flash_manager import FlashManager, FlashResult
from .plugin_system import Plugin, PluginManager, PluginInfo
from .openclaw_integration import ArduinoBridgeClient

__all__ = [
    # Core
    "list_ports",
    "filter_arduino_ports",
    "identify_board",
    "BoardInfo",
    "FlashManager",
    "FlashResult",
    # Plugins
    "Plugin",
    "PluginManager",
    "PluginInfo",
    # OpenClaw
    "ArduinoBridgeClient",
]

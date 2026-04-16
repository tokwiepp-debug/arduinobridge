"""
Example ArduinoBridge Plugin
This is a template demonstrating the plugin API.
"""

from arduino_bridge.plugin_system import Plugin


class ExamplePlugin(Plugin):
    """
    Example plugin that logs all events to console.
    Extend this to add your own functionality.
    """
    name = "ExamplePlugin"
    version = "0.1.0"
    description = "Example plugin demonstrating the plugin API"
    author = "ArduinoBridge"
    
    def on_port_detected(self, port_info: dict):
        """Called when a port is detected during scan"""
        print(f"[ExamplePlugin] Port detected: {port_info.get('port')} - {port_info.get('description')}")
    
    def on_port_removed(self, port: str):
        """Called when a port disappears"""
        print(f"[ExamplePlugin] Port removed: {port}")
    
    def on_board_identified(self, board_info: dict):
        """Called when a board is successfully identified"""
        print(f"[ExamplePlugin] Board identified: {board_info.get('board_name')} "
              f"({board_info.get('board_type')}) on {board_info.get('port')} "
              f"[confidence: {board_info.get('confidence', 0):.0%}]")
    
    def on_flash_start(self, port: str, board_type: str, firmware: str):
        """Called just before flashing begins"""
        print(f"[ExamplePlugin] Flash starting: {board_type} on {port} with {firmware}")
    
    def on_flash_progress(self, message: str, percentage: float):
        """Called during flash with progress updates"""
        print(f"[ExamplePlugin] Flash progress: {percentage:.0f}% - {message}")
    
    def on_flash_complete(self, result: dict):
        """Called after flash completes (success or failure)"""
        status = "SUCCESS" if result.get("success") else "FAILED"
        print(f"[ExamplePlugin] Flash {status}: {result.get('message', '')} "
              f"[duration: {result.get('duration_seconds', 0):.1f}s]")
    
    def on_firmware_uploaded(self, port: str, board_type: str, success: bool):
        """Called after firmware is uploaded"""
        status = "SUCCESS" if success else "FAILED"
        print(f"[ExamplePlugin] Firmware upload {status} to {board_type} on {port}")


# Plugin instance - must be named 'plugin'
plugin = ExamplePlugin()

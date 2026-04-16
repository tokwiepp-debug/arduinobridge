"""
Plugin System for ArduinoBridge
Load and manage extensions from the plugins/ directory
"""

import os
import sys
import logging
import importlib.util
import inspect
from typing import Dict, List, Optional, Any, Type
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PluginInfo:
    name: str
    version: str
    description: str = ""
    author: str = ""
    module_path: str = ""


class Plugin:
    """
    Base class for all ArduinoBridge plugins.
    Implement any of the lifecycle methods you need.
    """
    name: str = "BasePlugin"
    version: str = "0.0.0"
    description: str = ""
    author: str = ""
    
    def on_port_detected(self, port_info: dict) -> None:
        """Called when a port is detected during scan"""
        pass
    
    def on_port_removed(self, port: str) -> None:
        """Called when a port disappears"""
        pass
    
    def on_board_identified(self, board_info: dict) -> None:
        """Called when a board is successfully identified"""
        pass
    
    def on_flash_start(self, port: str, board_type: str, firmware: str) -> None:
        """Called just before flashing begins"""
        pass
    
    def on_flash_progress(self, message: str, percentage: float) -> None:
        """Called during flash with progress updates"""
        pass
    
    def on_flash_complete(self, result: dict) -> None:
        """Called after flash completes (success or failure)"""
        pass
    
    def on_firmware_uploaded(self, port: str, board_type: str, success: bool) -> None:
        """Called after firmware is uploaded"""
        pass


class PluginManager:
    """
    Manages plugin loading, lifecycle, and event dispatching.
    """
    
    def __init__(self, plugin_dir: str = None):
        if plugin_dir is None:
            # Default to plugins/ in same directory as this module
            self.plugin_dir = os.path.join(os.path.dirname(__file__), "plugins")
        else:
            self.plugin_dir = plugin_dir
        
        self.plugins: Dict[str, Plugin] = {}
        self.plugin_info: Dict[str, PluginInfo] = {}
        
        # Ensure plugins directory exists
        os.makedirs(self.plugin_dir, exist_ok=True)
        
        logger.info(f"PluginManager initialized. Plugin dir: {self.plugin_dir}")
    
    def load_plugin(self, plugin_name: str) -> bool:
        """
        Load a plugin by name (filename without .py extension).
        Returns True if loaded successfully.
        """
        plugin_path = os.path.join(self.plugin_dir, f"{plugin_name}.py")
        
        if not os.path.exists(plugin_path):
            logger.error(f"Plugin not found: {plugin_path}")
            return False
        
        if plugin_name in self.plugins:
            logger.warning(f"Plugin already loaded: {plugin_name}")
            return True
        
        try:
            # Load module from file
            spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
            if spec is None or spec.loader is None:
                logger.error(f"Could not load plugin spec: {plugin_name}")
                return False
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[plugin_name] = module
            spec.loader.exec_module(module)
            
            # Find Plugin class in module
            plugin_class = None
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, Plugin) and obj is not Plugin:
                    plugin_class = obj
                    break
            
            if plugin_class is None:
                logger.error(f"No Plugin subclass found in {plugin_name}")
                return False
            
            # Instantiate and register
            instance = plugin_class()
            self.plugins[plugin_name] = instance
            
            # Build info
            info = PluginInfo(
                name=getattr(instance, 'name', plugin_name),
                version=getattr(instance, 'version', '0.0.0'),
                description=getattr(instance, 'description', ''),
                author=getattr(instance, 'author', ''),
                module_path=plugin_path
            )
            self.plugin_info[plugin_name] = info
            
            logger.info(f"Loaded plugin: {info.name} v{info.version}")
            return True
            
        except Exception as e:
            logger.exception(f"Failed to load plugin {plugin_name}")
            return False
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a plugin"""
        if plugin_name not in self.plugins:
            logger.warning(f"Plugin not loaded: {plugin_name}")
            return False
        
        instance = self.plugins[plugin_name]
        if hasattr(instance, 'shutdown'):
            try:
                instance.shutdown()
            except Exception as e:
                logger.warning(f"Error shutting down plugin {plugin_name}: {e}")
        
        del self.plugins[plugin_name]
        del self.plugin_info[plugin_name]
        logger.info(f"Unloaded plugin: {plugin_name}")
        return True
    
    def load_all_plugins(self) -> List[str]:
        """Auto-load all .py files in the plugins directory"""
        loaded = []
        for filename in os.listdir(self.plugin_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                plugin_name = filename[:-3]
                if self.load_plugin(plugin_name):
                    loaded.append(plugin_name)
        return loaded
    
    def reload_plugin(self, plugin_name: str) -> bool:
        """Reload a plugin (unload then load)"""
        self.unload_plugin(plugin_name)
        return self.load_plugin(plugin_name)
    
    def get_plugin(self, plugin_name: str) -> Optional[Plugin]:
        """Get loaded plugin instance by name"""
        return self.plugins.get(plugin_name)
    
    def list_plugins(self) -> List[PluginInfo]:
        """List all loaded plugins with their info"""
        return list(self.plugin_info.values())
    
    # Event dispatch methods
    def notify_port_detected(self, port_info: dict) -> None:
        for plugin in self.plugins.values():
            try:
                plugin.on_port_detected(port_info)
            except Exception as e:
                logger.warning(f"Plugin {type(plugin).name} error in on_port_detected: {e}")
    
    def notify_port_removed(self, port: str) -> None:
        for plugin in self.plugins.values():
            try:
                plugin.on_port_removed(port)
            except Exception as e:
                logger.warning(f"Plugin {type(plugin).name} error in on_port_removed: {e}")
    
    def notify_board_identified(self, board_info: dict) -> None:
        for plugin in self.plugins.values():
            try:
                plugin.on_board_identified(board_info)
            except Exception as e:
                logger.warning(f"Plugin {type(plugin).name} error in on_board_identified: {e}")
    
    def notify_flash_start(self, port: str, board_type: str, firmware: str) -> None:
        for plugin in self.plugins.values():
            try:
                plugin.on_flash_start(port, board_type, firmware)
            except Exception as e:
                logger.warning(f"Plugin {type(plugin).name} error in on_flash_start: {e}")
    
    def notify_flash_progress(self, message: str, percentage: float) -> None:
        for plugin in self.plugins.values():
            try:
                plugin.on_flash_progress(message, percentage)
            except Exception as e:
                logger.warning(f"Plugin {type(plugin).name} error in on_flash_progress: {e}")
    
    def notify_flash_complete(self, result: dict) -> None:
        for plugin in self.plugins.values():
            try:
                plugin.on_flash_complete(result)
            except Exception as e:
                logger.warning(f"Plugin {type(plugin).name} error in on_flash_complete: {e}")


# Example plugin template
EXAMPLE_PLUGIN = '''
"""
Example ArduinoBridge Plugin
Copy this as a template for your own plugins
"""

from arduino_bridge.plugin_system import Plugin


class MyPlugin(Plugin):
    name = "ExamplePlugin"
    version = "0.1.0"
    description = "An example plugin demonstrating the plugin API"
    author = "Your Name"
    
    def on_port_detected(self, port_info: dict):
        print(f"Port detected: {port_info['port']}")
    
    def on_board_identified(self, board_info: dict):
        print(f"Board identified: {board_info['board_name']} on {board_info['port']}")
    
    def on_flash_complete(self, result: dict):
        status = "SUCCESS" if result.get("success") else "FAILED"
        print(f"Flash {status}: {result.get('message', '')}")


# Register plugin instance
plugin = MyPlugin()
'''


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    pm = PluginManager()
    
    # Create example plugin if plugins dir is empty
    example_path = os.path.join(pm.plugin_dir, "example_plugin.py")
    if not any(f.endswith(".py") for f in os.listdir(pm.plugin_dir) if not f.startswith("_")):
        print(f"Creating example plugin at: {example_path}")
        with open(example_path, "w") as f:
            f.write(EXAMPLE_PLUGIN)
    
    # Load all
    loaded = pm.load_all_plugins()
    print(f"\\nLoaded plugins: {loaded}")
    
    # List
    for info in pm.list_plugins():
        print(f"  - {info.name} v{info.version} by {info.author}")

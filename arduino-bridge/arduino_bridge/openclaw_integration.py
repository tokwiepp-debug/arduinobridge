"""
OpenClaw Integration Module
Allows Melissa to communicate with ArduinoBridge server
"""

import logging
import requests
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class ArduinoBridgeClient:
    """
    Client for the ArduinoBridge REST API.
    Used by Melissa/OpenClaw to interact with ArduinoBridge.
    """
    
    def __init__(self, base_url: str = "http://127.0.0.1:8765"):
        self.base_url = base_url.rstrip("/")
        self.timeout = 30
    
    def _get(self, endpoint: str) -> Dict[str, Any]:
        """Make GET request"""
        try:
            resp = requests.get(f"{self.base_url}{endpoint}", timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"Cannot connect to ArduinoBridge at {self.base_url}. Is the server running?")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Request failed: {e}")
    
    def _post(self, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make POST request"""
        try:
            resp = requests.post(f"{self.base_url}{endpoint}", json=data, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"Cannot connect to ArduinoBridge at {self.base_url}. Is the server running?")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Request failed: {e}")
    
    def health(self) -> bool:
        """Check if server is healthy"""
        try:
            return self._get("/health").get("status") == "ok"
        except:
            return False
    
    def list_ports(self) -> Dict[str, Any]:
        """List all ports"""
        return self._get("/ports")
    
    def list_arduino_ports(self) -> Dict[str, Any]:
        """List only Arduino ports"""
        return self._get("/ports/arduino")
    
    def identify_board(self, port: str) -> Dict[str, Any]:
        """Identify board on a port"""
        return self._get(f"/board?port={port}")
    
    def flash(self, port: str, board_type: str, firmware_path: str = None,
              firmware_hex: str = None, verify: bool = True) -> Dict[str, Any]:
        """
        Flash firmware to a board.
        
        Args:
            port: COM port or device path
            board_type: uno, mega, nano, etc.
            firmware_path: Path to firmware file
            firmware_hex: Alternative to firmware_path - hex string
            verify: Run verification after flash
        """
        data = {
            "port": port,
            "board_type": board_type,
            "verify": verify
        }
        if firmware_path:
            data["firmware_path"] = firmware_path
        if firmware_hex:
            data["firmware_hex"] = firmware_hex
        
        return self._post("/flash", data)
    
    def flash_status(self) -> Dict[str, Any]:
        """Check flash tool availability"""
        return self._get("/flash/status")
    
    def list_plugins(self) -> Dict[str, Any]:
        """List loaded plugins"""
        return self._get("/plugins")
    
    def load_plugin(self, name: str) -> Dict[str, Any]:
        """Load a plugin by name"""
        return self._post("/plugins/load", {"name": name})
    
    def scan_plugins(self) -> Dict[str, Any]:
        """Scan for available plugins"""
        return self._post("/plugins/scan", {})
    
    # === High-level helper methods ===
    
    def find_first_arduino(self) -> Optional[Dict[str, Any]]:
        """
        Find the first connected Arduino board.
        Returns port info or None if no Arduino found.
        """
        result = self.list_arduino_ports()
        ports = result.get("ports", [])
        if not ports:
            return None
        
        # Try to identify the first one
        for port_info in ports:
            try:
                board = self.identify_board(port_info["port"])
                if board.get("board_type") != "unknown" or board.get("confidence", 0) > 0.3:
                    return {
                        "port": port_info["port"],
                        "board": board
                    }
            except:
                continue
        
        # Fall back to just returning the first port
        return {"port": ports[0]["port"], "board": None}
    
    def get_status_summary(self) -> str:
        """Get a human-readable status summary"""
        lines = []
        
        # Health
        if self.health():
            lines.append("✓ ArduinoBridge server is running")
        else:
            lines.append("✗ ArduinoBridge server is not reachable")
            return "\n".join(lines)
        
        # Ports
        try:
            result = self.list_arduino_ports()
            count = result.get("count", 0)
            if count == 0:
                lines.append("  No Arduino boards detected")
            else:
                lines.append(f"  Found {count} Arduino board(s):")
                for p in result.get("ports", []):
                    lines.append(f"    - {p['port']} ({p.get('description', 'Unknown')})")
        except Exception as e:
            lines.append(f"  Error scanning ports: {e}")
        
        # Flash tools
        try:
            status = self.flash_status()
            tools = []
            if status.get("avrdude"):
                tools.append("avrdude")
            if status.get("platformio"):
                tools.append("platformio")
            if status.get("esptool"):
                tools.append("esptool")
            if tools:
                lines.append(f"  Flash tools: {', '.join(tools)}")
            else:
                lines.append("  No flash tools found")
        except:
            pass
        
        return "\n".join(lines)


if __name__ == "__main__":
    # Quick test
    client = ArduinoBridgeClient()
    
    print("=== ArduinoBridge Status ===\n")
    print(client.get_status_summary())

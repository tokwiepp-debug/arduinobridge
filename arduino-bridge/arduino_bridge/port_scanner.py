"""
Port Scanner - Detect COM/USB ports with Arduino devices
Cross-platform: Windows, Linux, macOS, Raspberry Pi
"""

import logging
import platform
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


def get_system() -> str:
    """Get the current operating system"""
    return platform.system().lower()


def list_ports() -> List[Dict[str, Any]]:
    """
    List all available serial ports on the system.
    
    Returns:
        List of dicts with keys: port, description, hwid,usb_info
    """
    import serial.tools.list_ports
    
    ports = []
    for port_info in serial.tools.list_ports.comports():
        port_data = {
            "port": port_info.device,
            "name": port_info.name,
            "description": port_info.description,
            "hwid": port_info.hwid,
            "location": getattr(port_info, "location", None),
            "manufacturer": getattr(port_info, "manufacturer", None),
            "product": getattr(port_info, "product", None),
            "serial_number": getattr(port_info, "serial_number", None),
            "usb_info": None
        }
        
        # Try to extract USB info
        if "usb" in port_data["hwid"].lower() or "usb" in (port_data["description"] or "").lower():
            port_data["usb_info"] = {
                "vid": extract_vid(port_data["hwid"]),
                "pid": extract_pid(port_data["hwid"]),
            }
        
        ports.append(port_data)
        logger.debug(f"Found port: {port_data}")
    
    return ports


def extract_vid(hwid: str) -> Optional[str]:
    """Extract Vendor ID from hardware ID string"""
    if not hwid:
        return None
    # Common formats: USB\VID_0403&PID_6001 or VID:0x0403
    import re
    match = re.search(r"VID[=_]([0-9A-Fa-f]{4})", hwid)
    if match:
        return match.group(1)
    match = re.search(r"0x([0-9A-Fa-f]{4})", hwid[:20])  # Often at start for USB
    if match:
        return match.group(1)
    return None


def extract_pid(hwid: str) -> Optional[str]:
    """Extract Product ID from hardware ID string"""
    if not hwid:
        return None
    import re
    match = re.search(r"PID[=_]([0-9A-Fa-f]{4})", hwid)
    if match:
        return match.group(1)
    return None


def is_arduino_port(port_info: Dict[str, Any]) -> bool:
    """
    Heuristics to detect if a port likely has an Arduino connected.
    """
    desc = (port_info.get("description") or "").lower()
    manufacturer = (port_info.get("manufacturer") or "").lower()
    product = (port_info.get("product") or "").lower()
    hwid = (port_info.get("hwid") or "").lower()
    
    # Known Arduino VID/PIDs
    arduino_vids = ["2341", "2a03", "1b4f", "239a"]  # Arduino, Arduino (clone), SparkFun
    
    vid = port_info.get("usb_info", {}).get("vid", "").lower()
    if vid in arduino_vids:
        return True
    
    # Check description strings
    arduino_keywords = ["arduino", "ftdi", "ch340", "ch341", "cp210", "pl2303"]
    for keyword in arduino_keywords:
        if keyword in desc or keyword in manufacturer or keyword in product:
            return True
    
    # Check hardware IDs for common USB-serial chips
    usb_serial_chips = ["0403:6001", "0403:6014", "10c4:ea60", "067b:2303", "1a86:7523"]
    for chip in usb_serial_chips:
        if chip.replace(":", "").lower() in hwid.replace(":", "").replace("_", "").lower():
            return True
    
    return False


def filter_arduino_ports(ports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter list to only include ports with likely Arduino devices"""
    return [p for p in ports if is_arduino_port(p)]


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.DEBUG)
    print(f"Platform: {get_system()}")
    print("\nAll ports:")
    for p in list_ports():
        print(f"  {p['port']} - {p['description']}")
    print("\nArduino ports:")
    for p in filter_arduino_ports(list_ports()):
        print(f"  {p['port']} - {p['description']}")

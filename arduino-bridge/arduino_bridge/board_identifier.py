"""
Board Identifier - Detect Arduino board type via USB descriptors and serial query
"""

import logging
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# Known Arduino board definitions
ARDUINO_BOARDS = {
    # VID:PID -> (board_name, board_type)
    "2341:0001": ("Arduino Uno", "uno"),
    "2341:0010": ("Arduino Mega", "mega"),
    "2341:003E": ("Arduino Nano", "nano"),
    "2341:003C": ("Arduino Mini", "mini"),
    "2341:003D": ("Arduino Pro Mini", "pro_mini"),
    "2341:003B": ("Arduino Duemilanove", "duemilanove"),
    "2341:0043": ("Arduino Uno SMD", "uno"),
    "2341:0042": ("Arduino Mega ADK", "mega_adk"),
    "2341:8036": ("Arduino Nano Every", "nano_every"),
    "2341:8057": ("Arduino Nano 33 BLE", "nano_33_ble"),
    "2341:8063": ("Arduino Nano 33 IoT", "nano_33_iot"),
    "2341:8078": ("Arduino Nano RP2040 Connect", "nano_rp2040"),
    "2A03:0001": ("Arduino Uno (Clone)", "uno"),
    "2A03:0040": ("Arduino Mega (Clone)", "mega"),
    "2A03:003E": ("Arduino Nano (Clone)", "nano"),
    "1B4F:0001": ("SparkFun Arduino", "uno"),  # SparkFun
    "239A:0001": ("Adafruit Arduino", "uno"),  # Adafruit
}


@dataclass
class BoardInfo:
    port: str
    board_name: str
    board_type: str
    vid: Optional[str] = None
    pid: Optional[str] = None
    serial_number: Optional[str] = None
    firmware_version: Optional[str] = None
    confidence: float = 0.0  # 0.0 - 1.0, how confident we are
    detection_method: str = "unknown"


def identify_from_usb(vid: str, pid: str) -> Optional[tuple]:
    """
    Identify board from USB Vendor ID and Product ID.
    
    Returns:
        (board_name, board_type) or None if unknown
    """
    if not vid or not pid:
        return None
    
    key = f"{vid.lower()}:{pid.lower()}"
    return ARDUINO_BOARDS.get(key)


def try_get_board_info(port_info: Dict[str, Any]) -> BoardInfo:
    """
    Identify board from port information dictionary.
    Tries multiple detection methods.
    """
    port = port_info["port"]
    vid = port_info.get("usb_info", {}).get("vid")
    pid = port_info.get("usb_info", {}).get("pid")
    
    # Method 1: USB VID/PID lookup
    if vid and pid:
        result = identify_from_usb(vid, pid)
        if result:
            board_name, board_type = result
            logger.info(f"Board identified via USB VID/PID: {board_name} on {port}")
            return BoardInfo(
                port=port,
                board_name=board_name,
                board_type=board_type,
                vid=vid,
                pid=pid,
                serial_number=port_info.get("serial_number"),
                confidence=0.95,
                detection_method="usb_vid_pid"
            )
    
    # Method 2: Description-based heuristics
    desc = (port_info.get("description") or "").lower()
    product = (port_info.get("product") or "").lower()
    
    if "mega" in desc or "mega" in product:
        return BoardInfo(port=port, board_name="Arduino Mega", board_type="mega",
                        vid=vid, pid=pid, confidence=0.7, detection_method="description")
    if "nano" in desc or "nano" in product:
        return BoardInfo(port=port, board_name="Arduino Nano", board_type="nano",
                        vid=vid, pid=pid, confidence=0.7, detection_method="description")
    if "uno" in desc or "uno" in product or "duemilanove" in desc:
        return BoardInfo(port=port, board_name="Arduino Uno", board_type="uno",
                        vid=vid, pid=pid, confidence=0.6, detection_method="description")
    if "leonardo" in desc or "leonardo" in product:
        return BoardInfo(port=port, board_name="Arduino Leonardo", board_type="leonardo",
                        vid=vid, pid=pid, confidence=0.7, detection_method="description")
    if "micro" in desc or "micro" in product:
        return BoardInfo(port=port, board_name="Arduino Micro", board_type="micro",
                        vid=vid, pid=pid, confidence=0.7, detection_method="description")
    if "esp32" in desc or "esp32" in product:
        return BoardInfo(port=port, board_name="ESP32 Dev Board", board_type="esp32",
                        vid=vid, pid=pid, confidence=0.8, detection_method="description")
    if "esp8266" in desc or "esp8266" in product:
        return BoardInfo(port=port, board_name="ESP8266", board_type="esp8266",
                        vid=vid, pid=pid, confidence=0.8, detection_method="description")
    
    # Method 3: Manufacturer check
    manufacturer = (port_info.get("manufacturer") or "").lower()
    if "arduino" in manufacturer:
        return BoardInfo(port=port, board_name="Arduino (Unknown Model)", board_type="unknown",
                        vid=vid, pid=pid, confidence=0.5, detection_method="manufacturer")
    
    # Unknown
    return BoardInfo(port=port, board_name="Unknown", board_type="unknown",
                    vid=vid, pid=pid, confidence=0.1, detection_method="none")


def identify_board(port: str, timeout: float = 1.0) -> BoardInfo:
    """
    Full board identification: try serial communication as fallback.
    
    On some boards (e.g. Leonardo, Micro) the USB serial port appears
    before the sketch is running. The board may need a reset or
    we can try querying it.
    """
    import serial
    
    # Get port info first
    from .port_scanner import list_ports
    ports = list_ports()
    port_info = next((p for p in ports if p["port"] == port), None)
    
    if not port_info:
        return BoardInfo(port=port, board_name="Unknown", board_type="unknown",
                        confidence=0.0, detection_method="not_found")
    
    # Try via USB descriptors first
    board = try_get_board_info(port_info)
    if board.confidence >= 0.9:
        return board
    
    # Try serial communication - send empty line, look for response
    try:
        with serial.Serial(port, 115200, timeout=timeout) as ser:
            time.sleep(0.1)  # Wait for board to initialize
            ser.write(b"\r\n")
            time.sleep(0.2)
            
            if ser.in_waiting > 0:
                response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                logger.debug(f"Serial response from {port}: {response[:100]}")
                
                # Parse response for board info
                if "Arduino" in response or "arduino" in response:
                    board.detection_method = "serial_response"
                    board.firmware_version = extract_firmware_version(response)
                    board.confidence = max(board.confidence, 0.6)
    except Exception as e:
        logger.debug(f"Could not query {port} via serial: {e}")
    
    return board


def extract_firmware_version(response: str) -> Optional[str]:
    """Try to extract firmware version from serial response"""
    import re
    # Common patterns
    patterns = [
        r"Firmware\s*v?(\d+\.\d+(?:\.\d+)?)",
        r"Version\s*v?(\d+\.\d+(?:\.\d+)?)",
        r"v(\d+\.\d+(?:\.\d+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, response, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    if len(sys.argv) > 1:
        port = sys.argv[1]
        print(f"Identifying board on {port}...")
        board = identify_board(port)
        print(f"Result: {board}")
    else:
        print("Usage: board_identifier.py <port>")

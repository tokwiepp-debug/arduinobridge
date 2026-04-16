"""
Flash Manager - Upload firmware to Arduino boards
Supports avrdude, bossac, and platformio
"""

import logging
import os
import platform
import subprocess
import tempfile
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FlashResult:
    success: bool
    message: str
    duration_seconds: float
    board_type: str
    port: str
    method: str
    output: str = ""


class FlashManager:
    """
    Handles firmware flashing to Arduino boards.
    Supports multiple backends: avrdude, bossac, esptool, platformio
    """
    
    def __init__(self, avrdude_path: Optional[str] = None, 
                 platformio_path: Optional[str] = None):
        self.system = platform.system().lower()
        self.avrdude_path = avrdude_path or self._find_avrdude()
        self.platformio_path = platformio_path or self._find_platformio()
        self.esptool_path = self._find_esptool()
        
        # Progress callback
        self._progress_callback: Optional[Callable[[str, float], None]] = None
    
    def set_progress_callback(self, callback: Callable[[str, float], None]):
        """Set callback for progress updates: callback(message, percentage)"""
        self._progress_callback = callback
    
    def _report(self, msg: str, pct: float = 0):
        """Report progress"""
        logger.debug(msg)
        if self._progress_callback:
            self._progress_callback(msg, pct)
    
    def _find_avrdude(self) -> Optional[str]:
        """Find avrdude on the system"""
        paths = []
        
        if self.system == "windows":
            paths.extend([
                "avrdude.exe",
                "C:\\Program Files\\Arduino\\hardware\\tools\\avr\\bin\\avrdude.exe",
                "C:\\Program Files (x86)\\Arduino\\hardware\\tools\\avr\\bin\\avrdude.exe",
            ])
        elif self.system == "linux":
            paths.extend(["avrdude", "/usr/bin/avrdude", "/usr/local/bin/avrdude"])
        elif self.system == "darwin":
            paths.extend(["avrdude", "/Applications/Arduino.app/Contents/Java/hardware/tools/avr/bin/avrdude"])
        
        for path in paths:
            try:
                result = subprocess.run([path, "-?",], 
                                      capture_output=True, 
                                      timeout=5)
                if result.returncode == 0 or result.returncode == 1:
                    logger.info(f"Found avrdude at: {path}")
                    return path
            except:
                continue
        return None
    
    def _find_platformio(self) -> Optional[str]:
        """Find platformio on the system"""
        import shutil
        path = shutil.which("platformio")
        if path:
            logger.info(f"Found platformio at: {path}")
        return path
    
    def _find_esptool(self) -> Optional[str]:
        """Find esptool on the system"""
        import shutil
        path = shutil.which("esptool.py") or shutil.which("esptool")
        if path:
            logger.info(f"Found esptool at: {path}")
        return path
    
    def flash(self, port: str, board_type: str, firmware_path: Optional[str] = None,
              firmware_hex: Optional[str] = None, verify: bool = True) -> FlashResult:
        """
        Flash firmware to a board.
        
        Args:
            port: COM port or device path
            board_type: uno, mega, nano, leonardo, esp32, esp8266, etc.
            firmware_path: Path to .hex or .bin file (optional if firmware_hex provided)
            firmware_hex: Hex string of firmware (alternative to firmware_path)
            verify: Run verification after flash
        
        Returns:
            FlashResult with success status and details
        """
        import time
        start = time.time()
        
        # Normalize board type
        board_type = board_type.lower().strip()
        
        # Use firmware_path or write firmware_hex to temp file
        if firmware_hex:
            with tempfile.NamedTemporaryFile(suffix=".hex", delete=False) as f:
                f.write(firmware_hex.encode() if isinstance(firmware_hex, str) else firmware_hex)
                firmware_path = f.name
        
        try:
            # Detect if ESP-based board
            if board_type in ("esp32", "esp8266", "esp32-s2", "esp32-s3", "esp32-c3"):
                return self._flash_esptool(port, board_type, firmware_path, verify, start)
            
            # Detect if ARM-based (Due, Zero, etc.)
            elif board_type in ("due", "zero", "mkr"):
                return self._flash_bossac(port, board_type, firmware_path, verify, start)
            
            # Default: AVR-based (Uno, Mega, Nano, Leonardo, etc.)
            else:
                return self._flash_avrdude(port, board_type, firmware_path, verify, start)
                
        except Exception as e:
            logger.exception("Flash failed")
            return FlashResult(
                success=False,
                message=f"Flash failed: {str(e)}",
                duration_seconds=time.time() - start,
                board_type=board_type,
                port=port,
                method="error"
            )
        finally:
            # Clean up temp file if we created one
            if firmware_hex and firmware_path and os.path.exists(firmware_path):
                try:
                    os.unlink(firmware_path)
                except:
                    pass
    
    def _flash_avrdude(self, port: str, board_type: str, 
                       firmware_path: Optional[str], verify: bool, start: float) -> FlashResult:
        """Flash AVR-based Arduino boards using avrdude"""
        
        if not self.avrdude_path:
            return FlashResult(
                success=False,
                message="avrdude not found. Install Arduino IDE or add avrdude to PATH.",
                duration_seconds=time.time() - start,
                board_type=board_type,
                port=port,
                method="avrdude"
            )
        
        # AVRDUDE config path
        if self.system == "windows":
            avrdude_conf_paths = [
                "C:\\Program Files\\Arduino\\hardware\\tools\\avr\\etc\\avrdude.conf",
                "C:\\Program Files (x86)\\Arduino\\hardware\\tools\\avr\\etc\\avrdude.conf",
            ]
        else:
            avrdude_conf_paths = ["/etc/avrdude.conf"]
        
        avrdude_conf = None
        for p in avrdude_conf_paths:
            if os.path.exists(p):
                avrdude_conf = p
                break
        
        # Programmer and config
        programmer = "arduino"
        
        # Board-specific settings
        board_configs = {
            "uno": ("m328p", "115200"),
            "mega": ("m2560", "115200"),
            "nano": ("m328p", "57600"),  # Old bootloader
            "nano_old": ("m328p", "19200"),
            "leonardo": ("m32u4", "115200"),
            "micro": ("m32u4", "115200"),
            "mini": ("m328p", "115200"),
            "pro_mini": ("m328p", "57600"),
        }
        
        mcu, speed = board_configs.get(board_type, ("m328p", "115200"))
        
        if not firmware_path:
            return FlashResult(
                success=False,
                message="No firmware file provided",
                duration_seconds=time.time() - start,
                board_type=board_type,
                port=port,
                method="avrdude"
            )
        
        self._report("Flashing with avrdude...", 10)
        
        cmd = [
            self.avrdude_path,
            "-C" + avrdude_conf if avrdude_conf else "",
            "-v",  # Verbose
            "-p" + mcu,
            "-c" + programmer,
            "-P" + port,
            "-b" + speed,
            "-D",  # Don't erase
            "-U", f"flash:w:{firmware_path}:i"
        ]
        cmd = [c for c in cmd if c]  # Remove empty strings
        
        self._report("Uploading firmware...", 30)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            self._report("Verifying...", 90)
            
            output = result.stdout + result.stderr
            
            if result.returncode == 0:
                success = True
                msg = "Flash successful"
            else:
                success = False
                msg = f"Flash failed (exit {result.returncode})"
            
            return FlashResult(
                success=success,
                message=msg,
                duration_seconds=time.time() - start,
                board_type=board_type,
                port=port,
                method="avrdude",
                output=output
            )
            
        except subprocess.TimeoutExpired:
            return FlashResult(
                success=False,
                message="Flash timed out after 120 seconds",
                duration_seconds=time.time() - start,
                board_type=board_type,
                port=port,
                method="avrdude"
            )
    
    def _flash_bossac(self, port: str, board_type: str,
                      firmware_path: Optional[str], verify: bool, start: float) -> FlashResult:
        """Flash ARM-based Arduino boards (Due, Zero, MKR) using bossac"""
        # bossac is typically found in Arduino install or system
        bossac_path = None
        
        if self.system == "windows":
            possible = "C:\\Program Files\\Arduino\\hardware\\tools\\bossac.exe"
            if os.path.exists(possible):
                bossac_path = possible
        
        if not firmware_path:
            return FlashResult(
                success=False,
                message="No firmware file provided",
                duration_seconds=time.time() - start,
                board_type=board_type,
                port=port,
                method="bossac"
            )
        
        cmd = [bossac_path or "bossac", "-i", "-d", "--port=" + port, "-U", "true", "-e", "-w", "-v", "-b", firmware_path]
        
        self._report("Flashing with bossac...", 20)
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            success = result.returncode == 0
            return FlashResult(
                success=success,
                message="Flash successful" if success else f"Flash failed: {result.stderr}",
                duration_seconds=time.time() - start,
                board_type=board_type,
                port=port,
                method="bossac",
                output=result.stdout + result.stderr
            )
        except FileNotFoundError:
            return FlashResult(
                success=False,
                message="bossac not found. Install Arduino Create or add bossac to PATH.",
                duration_seconds=time.time() - start,
                board_type=board_type,
                port=port,
                method="bossac"
            )
        except subprocess.TimeoutExpired:
            return FlashResult(
                success=False,
                message="Flash timed out",
                duration_seconds=time.time() - start,
                board_type=board_type,
                port=port,
                method="bossac"
            )
    
    def _flash_esptool(self, port: str, board_type: str,
                       firmware_path: Optional[str], verify: bool, start: float) -> FlashResult:
        """Flash ESP32/ESP8266 using esptool"""
        
        if not self.esptool_path and not self.platformio_path:
            return FlashResult(
                success=False,
                message="esptool.py or platformio not found. Install ESP32 Arduino core.",
                duration_seconds=time.time() - start,
                board_type=board_type,
                port=port,
                method="esptool"
            )
        
        if not firmware_path:
            return FlashResult(
                success=False,
                message="No firmware .bin file provided for ESP",
                duration_seconds=time.time() - start,
                board_type=board_type,
                port=port,
                method="esptool"
            )
        
        # esptool.py options
        cmd = [
            self.esptool_path or "esptool.py",
            "--chip", board_type,
            "--port", port,
            "--baud", "921600",
            "--before", "default_reset",
            "--after", "hard_reset", "write_flash",
            "0x1000", firmware_path  # Bootloader offset varies
        ]
        
        self._report("Flashing ESP with esptool...", 10)
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            success = result.returncode == 0
            return FlashResult(
                success=success,
                message="Flash successful" if success else f"Flash failed: {result.stderr}",
                duration_seconds=time.time() - start,
                board_type=board_type,
                port=port,
                method="esptool",
                output=result.stdout + result.stderr
            )
        except FileNotFoundError:
            return FlashResult(
                success=False,
                message="esptool.py not found",
                duration_seconds=time.time() - start,
                board_type=board_type,
                port=port,
                method="esptool"
            )
        except subprocess.TimeoutExpired:
            return FlashResult(
                success=False,
                message="Flash timed out",
                duration_seconds=time.time() - start,
                board_type=board_type,
                port=port,
                method="esptool"
            )


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    
    fm = FlashManager()
    
    if len(sys.argv) > 3:
        port = sys.argv[1]
        board = sys.argv[2]
        firmware = sys.argv[3]
        print(f"Flashing {firmware} to {port} ({board})...")
        result = fm.flash(port, board, firmware)
        print(f"Success: {result.success}")
        print(f"Message: {result.message}")
        print(f"Duration: {result.duration_seconds:.1f}s")
    else:
        print("Usage: flash_manager.py <port> <board_type> <firmware.hex>")

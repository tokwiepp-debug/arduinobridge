#!/usr/bin/env python3
"""
ArduinoBridge GUI - Desktop App for Arduino Programming via Melissa
Tkinter-based GUI with COM port selection, board detection, and flash capability
"""

import os
import sys
import json
import time
import threading
import logging
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("arduino-bridge-gui")

VERSION = "0.1.0"

# Try importing optional deps
try:
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    logger.warning("pyserial not available - COM port scanning disabled")

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("requests not available - OpenClaw connectivity disabled")

OPENCLAW_API = os.environ.get("OPENCLAW_API", "http://127.0.0.1:18789")


class ArduinoBridgeGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"ArduinoBridge GUI v{VERSION}")
        self.root.geometry("700x600")
        self.root.resizable(True, True)
        
        self.selected_port = tk.StringVar(value="")
        self.selected_board = tk.StringVar(value="Unknown")
        self.board_confidence = tk.DoubleVar(value=0.0)
        self.connection_status = tk.StringVar(value="Disconnected")
        self.openclaw_status = tk.StringVar(value="Unknown")
        self.refresh_running = False
        self.refresh_thread = None
        
        self._build_ui()
        self._start_auto_refresh()
    
    def _build_ui(self):
        # Style
        style = ttk.Style()
        style.theme_use('clam')
        
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # === Header ===
        header = ttk.Label(main_frame, text=f"ArduinoBridge GUI v{VERSION}", font=("Helvetica", 16, "bold"))
        header.grid(row=0, column=0, columnspan=3, pady=(0, 10))
        
        # === Connection Status Section ===
        conn_frame = ttk.LabelFrame(main_frame, text="Connection Status", padding="10")
        conn_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        
        ttk.Label(conn_frame, text="OpenClaw:").grid(row=0, column=0, sticky="w")
        ttk.Label(conn_frame, textvariable=self.openclaw_status, foreground="gray").grid(row=0, column=1, sticky="w", padx=(10, 0))
        
        ttk.Label(conn_frame, text="ArduinoBridge Server:").grid(row=1, column=0, sticky="w")
        ttk.Label(conn_frame, textvariable=self.connection_status, foreground="gray").grid(row=1, column=1, sticky="w", padx=(10, 0))
        
        # === COM Port Section ===
        port_frame = ttk.LabelFrame(main_frame, text="COM Port Selection", padding="10")
        port_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        
        ttk.Label(port_frame, text="Available Ports:").grid(row=0, column=0, sticky="w")
        
        # Port listbox with scrollbar
        list_frame = ttk.Frame(port_frame)
        list_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        
        self.port_listbox = tk.Listbox(list_frame, height=6, yscrollcommand=scrollbar.set, exportselection=0)
        self.port_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.port_listbox.yview)
        
        self.port_listbox.bind("<<ListboxSelect>>", self._on_port_selected)
        
        # Refresh button
        ttk.Button(port_frame, text="🔄 Refresh Ports", command=self._refresh_ports).grid(row=2, column=0, columnspan=2, pady=(10, 0))
        
        # Manual port entry
        ttk.Label(port_frame, text="Manual port:").grid(row=3, column=0, sticky="w", pady=(10, 0))
        self.manual_port = ttk.Entry(port_frame, width=15)
        self.manual_port.grid(row=3, column=1, sticky="w", pady=(10, 0))
        self.manual_port.insert(0, "COM3")
        ttk.Button(port_frame, text="Use Manual", command=self._use_manual_port).grid(row=3, column=1, sticky="e", padx=(80, 0), pady=(10, 0))
        
        # === Board Detection Section ===
        board_frame = ttk.LabelFrame(main_frame, text="Board Detection", padding="10")
        board_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        
        ttk.Label(board_frame, text="Detected Board:").grid(row=0, column=0, sticky="w")
        ttk.Label(board_frame, textvariable=self.selected_board, font=("Helvetica", 12, "bold")).grid(row=0, column=1, sticky="w", padx=(10, 0))
        
        ttk.Label(board_frame, text="Confidence:").grid(row=1, column=0, sticky="w")
        ttk.Label(board_frame, textvariable=self.board_confidence, foreground="gray").grid(row=1, column=1, sticky="w", padx=(10, 0))
        
        # Board override
        ttk.Label(board_frame, text="Manual board:").grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.board_combo = ttk.Combobox(board_frame, values=[
            "uno", "mega", "nano", "nano_old", "leonardo", "micro", 
            "mini", "pro_mini", "due", "esp32", "esp8266", "unknown"
        ], width=15, state="readonly")
        self.board_combo.grid(row=2, column=1, sticky="w", padx=(10, 0), pady=(10, 0))
        self.board_combo.current(0)
        self.board_combo.bind("<<ComboboxSelected>>", self._on_board_changed)
        
        ttk.Button(board_frame, text="🔍 Identify Board", command=self._identify_board).grid(row=3, column=0, columnspan=2, pady=(10, 0))
        
        # === Control Buttons ===
        ctrl_frame = ttk.Frame(main_frame)
        ctrl_frame.grid(row=4, column=0, columnspan=3, pady=(0, 10))
        
        self.connect_btn = ttk.Button(ctrl_frame, text="▶ Connect to Melissa", command=self._toggle_connection, style="Accent.TButton")
        self.connect_btn.pack(side="left", padx=(0, 5))
        
        ttk.Button(ctrl_frame, text="⚡ Flash Firmware", command=self._flash_firmware).pack(side="left", padx=(0, 5))
        ttk.Button(ctrl_frame, text="🗑 Clear Logs", command=self._clear_logs).pack(side="left")
        
        # === Log Window ===
        log_frame = ttk.LabelFrame(main_frame, text="Log Output", padding="5")
        log_frame.grid(row=5, column=0, columnspan=3, sticky="nsew", pady=(0, 0))
        
        main_frame.rowconfigure(5, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.columnconfigure(2, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, wrap="word", font=("Courier", 9))
        self.log_text.pack(fill="both", expand=True)
        
        # Configure text colors
        self.log_text.tag_config("INFO", foreground="black")
        self.log_text.tag_config("WARNING", foreground="orange")
        self.log_text.tag_config("ERROR", foreground="red")
        self.log_text.tag_config("SUCCESS", foreground="green")
        self.log_text.tag_config("SYSTEM", foreground="blue")
        
        # Status bar
        self.status_bar = ttk.Label(main_frame, text="Ready", relief="sunken", anchor="w")
        self.status_bar.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(5, 0))
        
        self._log("SYSTEM", f"ArduinoBridge GUI v{VERSION} started")
        self._log("SYSTEM", f"OpenClaw API: {OPENCLAW_API}")
        self._check_openclaw_status()
    
    def _log(self, level, message):
        """Add log message to log window"""
        timestamp = time.strftime("%H:%M:%S")
        line = f"[{timestamp}] [{level}] {message}\n"
        
        self.log_text.insert("end", line, level)
        self.log_text.see("end")
        
        # Also print to console
        getattr(logger, level.lower(), logger.info)(message)
    
    def _status(self, message):
        """Update status bar"""
        self.status_bar.config(text=message)
    
    def _refresh_ports(self):
        """Scan for available COM ports"""
        self._log("INFO", "Scanning for COM ports...")
        self.port_listbox.delete(0, "end")
        
        if not SERIAL_AVAILABLE:
            self._log("WARNING", "pyserial not installed - cannot scan ports")
            return
        
        try:
            ports = list(serial.tools.list_ports.comports())
            if not ports:
                self._log("INFO", "No COM ports found")
                return
            
            for port in ports:
                desc = port.description or "Unknown"
                self.port_listbox.insert("end", f"{port.device} - {desc}")
                self._log("SYSTEM", f"Found: {port.device} ({desc})")
            
            self._log("SUCCESS", f"Found {len(ports)} port(s)")
        except Exception as e:
            self._log("ERROR", f"Port scan failed: {e}")
    
    def _on_port_selected(self, event):
        """Handle port selection"""
        selection = self.port_listbox.curselection()
        if selection:
            text = self.port_listbox.get(selection[0])
            port = text.split(" - ")[0]
            self.selected_port.set(port)
            self._log("INFO", f"Selected port: {port}")
            self._status(f"Port: {port}")
    
    def _use_manual_port(self):
        """Use manually entered port"""
        port = self.manual_port.get().strip()
        if port:
            self.selected_port.set(port)
            self._log("INFO", f"Manual port set: {port}")
            self._status(f"Manual port: {port}")
    
    def _on_board_changed(self, event):
        """Handle board selection change"""
        board = self.board_combo.get()
        self.selected_board.set(board)
        self._log("INFO", f"Board changed to: {board}")
    
    def _identify_board(self):
        """Identify board on selected port"""
        port = self.selected_port.get()
        if not port:
            self._log("WARNING", "No port selected")
            messagebox.showwarning("No Port", "Please select or enter a COM port first")
            return
        
        self._log("INFO", f"Identifying board on {port}...")
        
        def identify_thread():
            try:
                # Try serial communication
                if SERIAL_AVAILABLE:
                    import serial
                    with serial.Serial(port, 115200, timeout=1) as ser:
                        ser.write(b"\r\n")
                        time.sleep(0.2)
                        if ser.in_waiting > 0:
                            response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                            self._log("SYSTEM", f"Response: {response[:100]}")
                            
                            # Heuristics
                            if "Arduino" in response or "Mega" in response:
                                self.selected_board.set("Arduino Mega")
                                self.board_confidence.set(0.7)
                            elif "Uno" in response:
                                self.selected_board.set("Arduino Uno")
                                self.board_confidence.set(0.7)
                            elif "Nano" in response:
                                self.selected_board.set("Arduino Nano")
                                self.board_confidence.set(0.7)
                            else:
                                self.selected_board.set("Arduino (Unknown)")
                                self.board_confidence.set(0.3)
                        else:
                            self.selected_board.set("Arduino (No Response)")
                            self.board_confidence.set(0.2)
                else:
                    # Fallback
                    self.selected_board.set("Unknown")
                    self.board_confidence.set(0)
                    
                self._log("SUCCESS", f"Board: {self.selected_board.get()} ({self.board_confidence.get():.0%} confidence)")
            except Exception as e:
                self._log("ERROR", f"Identify failed: {e}")
        
        threading.Thread(target=identify_thread, daemon=True).start()
    
    def _check_openclaw_status(self):
        """Check if OpenClaw gateway is reachable"""
        if not REQUESTS_AVAILABLE:
            self.openclaw_status.set("requests not available")
            return
        
        try:
            resp = requests.get(f"{OPENCLAW_API}/health", timeout=3)
            if resp.status_code == 200:
                self.openclaw_status.set("✓ Connected")
                self.connection_status.set("✓ Running")
                self._log("SUCCESS", "OpenClaw gateway is reachable")
            else:
                self.openclaw_status.set(f"✗ HTTP {resp.status_code}")
                self._log("WARNING", f"OpenClaw returned status {resp.status_code}")
        except Exception as e:
            self.openclaw_status.set("✗ Not reachable")
            self._log("WARNING", f"Cannot reach OpenClaw: {e}")
    
    def _toggle_connection(self):
        """Toggle connection to OpenClaw"""
        if self.refresh_running:
            self.refresh_running = False
            self.connect_btn.config(text="▶ Connect to Melissa")
            self._log("SYSTEM", "Disconnected from auto-refresh")
        else:
            self.refresh_running = True
            self.connect_btn.config(text="⏹ Disconnect")
            self._start_connection_loop()
            self._log("SYSTEM", "Connected - starting auto-refresh")
    
    def _start_connection_loop(self):
        """Background loop for connection monitoring"""
        def loop():
            while self.refresh_running:
                self._check_openclaw_status()
                self._refresh_ports()
                time.sleep(5)  # Refresh every 5 seconds
        
        threading.Thread(target=loop, daemon=True).start()
    
    def _flash_firmware(self):
        """Flash firmware to Arduino"""
        port = self.selected_port.get()
        board = self.board_combo.get()
        
        if not port:
            messagebox.showwarning("No Port", "Please select a port first")
            return
        
        self._log("INFO", f"Flash requested for {board} on {port}")
        self._log("SYSTEM", "Flash functionality - send hex content or select firmware file")
        messagebox.showinfo("Flash", f"Board: {board}\nPort: {port}\n\nUse the /flash command in Melissa to upload firmware.")
    
    def _clear_logs(self):
        """Clear log window"""
        self.log_text.delete(1.0, "end")
        self._log("SYSTEM", "Logs cleared")
    
    def _start_auto_refresh(self):
        """Initial port scan"""
        self._refresh_ports()
        
        # Initial OpenClaw check
        if REQUESTS_AVAILABLE:
            threading.Thread(target=self._check_openclaw_status, daemon=True).start()


def main():
    root = tk.Tk()
    app = ArduinoBridgeGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

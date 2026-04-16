#!/usr/bin/env python3
"""
ArduinoBridge GUI - Modern Dark Theme Desktop App
Connects to Melissa/OpenClaw Gateway and accepts flash commands
"""

import os
import sys
import json
import time
import threading
import logging
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import urllib.request
import urllib.error
import websocket  # pip install websocket-client

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("arduino-bridge-gui")

VERSION = "0.3.0"

# OpenClaw Gateway Config
OPENCLAW_HOST = os.environ.get("OPENCLAW_HOST", "192.168.178.25")
OPENCLAW_PORT = os.environ.get("OPENCLAW_PORT", "18789")
OPENCLAW_WS = f"ws://{OPENCLAW_HOST}:{OPENCLAW_PORT}"
OPENCLAW_HTTP = f"http://{OPENCLAW_HOST}:{OPENCLAW_PORT}"

# Try imports
try:
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

logger.info(f"ArduinoBridge GUI v{VERSION} starting...")
logger.info(f"OpenClaw Gateway: {OPENCLAW_WS}")


# ========================
# MODERN DARK THEME STYLES
# ========================

DARK_BG = "#1e1e2e"
DARK_CARD = "#2a2a3e"
DARK_ACCENT = "#7c3aed"
DARK_SUCCESS = "#10b981"
DARK_ERROR = "#ef4444"
DARK_WARNING = "#f59e0b"
DARK_TEXT = "#e2e8f0"
DARK_MUTED = "#94a3b8"
DARK_BORDER = "#3f3f5a"


class MelissaConnection:
    """WebSocket connection to Melissa/OpenClaw Gateway"""
    
    def __init__(self, gui):
        self.gui = gui
        self.ws = None
        self.connected = False
        self.running = False
        self.reconnect_delay = 3
    
    def connect(self):
        """Connect to Melissa gateway"""
        self.running = True
        thread = threading.Thread(target=self._connect_loop, daemon=True)
        thread.start()
    
    def _connect_loop(self):
        """Reconnection loop"""
        while self.running:
            try:
                self._log("SYSTEM", f"Connecting to Melissa gateway...")
                
                # Create WebSocket connection
                self.ws = websocket.WebSocketApp(
                    OPENCLAW_WS,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close
                )
                
                # Run forever (blocking)
                self.ws.run_forever(ping_interval=15, ping_timeout=5)
                
            except Exception as e:
                self._log("ERROR", f"Connection error: {e}")
            
            if self.running:
                self._log("WARNING", f"Reconnecting in {self.reconnect_delay}s...")
                time.sleep(self.reconnect_delay)
    
    def _on_open(self, ws):
        """Called when WebSocket opens"""
        self._log("SYSTEM", "WebSocket opened!")
        
        # Send connect request
        import uuid
        connect_req = {
            "type": "req",
            "id": str(uuid.uuid4()),
            "method": "connect",
            "params": {
                "minProtocol": 3,
                "maxProtocol": 3,
                "client": {
                    "id": "arduino-bridge-gui",
                    "version": VERSION,
                    "platform": "windows",
                    "mode": "device"
                },
                "role": "node",
                "scopes": ["arduino.flash", "arduino.scan", "arduino.identify"],
                "caps": ["arduino"],
                "commands": ["flash", "scan", "identify"],
                "permissions": {},
                "locale": "de-DE",
                "userAgent": f"arduino-bridge-gui/{VERSION}"
            }
        }
        
        ws.send(json.dumps(connect_req))
        self._log("SYSTEM", "Sent connect request to Melissa")
    
    def _on_message(self, ws, message):
        """Handle incoming messages from Melissa"""
        try:
            data = json.loads(message)
            self._log("MELISSA", f"Received: {data.get('method', data.get('type', 'unknown'))}")
            
            # Handle different message types
            msg_type = data.get("type")
            method = data.get("method")
            
            if msg_type == "res" and data.get("ok"):
                payload = data.get("payload", {})
                if payload.get("type") == "hello-ok":
                    self.connected = True
                    self.gui._on_connected()
                    self._log("SUCCESS", "✓ Connected to Melissa!")
                    return
                
            elif method in ("arduino.flash", "flash"):
                # Melissa wants us to flash
                params = data.get("params", {})
                self.gui._handle_flash_command(params)
                
            elif method in ("arduino.scan", "scan"):
                # Melissa wants port scan
                result = self.gui._do_scan()
                self._send_response(data, {"success": True, "ports": result})
                
            elif method in ("arduino.identify", "identify"):
                # Melissa wants board identification
                params = data.get("params", {})
                result = self.gui._do_identify(params.get("port"))
                self._send_response(data, result)
                
            elif method == "ping":
                self._send_response(data, {"pong": True})
                
        except Exception as e:
            self._log("ERROR", f"Message handling error: {e}")
    
    def _on_error(self, ws, error):
        """Handle WebSocket errors"""
        self._log("ERROR", f"WebSocket error: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Called when WebSocket closes"""
        self.connected = False
        self.gui._on_disconnected()
        self._log("WARNING", f"Disconnected: {close_status_code} - {close_msg}")
    
    def _send_response(self, request, result):
        """Send response to Melissa"""
        if not self.ws or not self.connected:
            return
        
        try:
            response = {
                "type": "res",
                "id": request.get("id", ""),
                "ok": True,
                "payload": result
            }
            self.ws.send(json.dumps(response))
        except Exception as e:
            self._log("ERROR", f"Failed to send response: {e}")
    
    def send_event(self, event_type, data):
        """Send event to Melissa"""
        if not self.ws or not self.connected:
            return
        
        try:
            event = {
                "type": "event",
                "event": event_type,
                "payload": data
            }
            self.ws.send(json.dumps(event))
        except Exception as e:
            self._log("ERROR", f"Failed to send event: {e}")
    
    def _log(self, level, message):
        self.gui._log(level, message)
    
    def disconnect(self):
        """Stop connection"""
        self.running = False
        if self.ws:
            self.ws.close()


class ModernGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"🔌 ArduinoBridge GUI v{VERSION}")
        self.root.configure(bg=DARK_BG)
        self.root.geometry("800x700")
        self.root.minsize(700, 600)
        
        # State
        self.serial_connected = False
        self.refresh_timer = None
        self.melissa = MelissaConnection(self)
        
        # Build UI
        self._build_ui()
        
        # Start connection to Melissa
        self._after(500, self._connect_to_melissa)
        self._after(2000, self._refresh_ports)
    
    def _build_ui(self):
        self._setup_styles()
        
        main = tk.Frame(self.root, bg=DARK_BG, padx=20, pady=20)
        main.pack(fill="both", expand=True)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # ===== HEADER =====
        header = tk.Frame(main, bg=DARK_BG)
        header.pack(fill="x", pady=(0, 15))
        
        tk.Label(header, text="🔌 ArduinoBridge", font=("Segoe UI", 20, "bold"),
                bg=DARK_BG, fg=DARK_TEXT).pack(side="left")
        
        tk.Label(header, text=f"v{VERSION}", font=("Segoe UI", 10),
                bg=DARK_BG, fg=DARK_MUTED).pack(side="left", pady=(12, 0), padx=(8, 0))
        
        # Connection indicator
        self.conn_frame = tk.Frame(header, bg=DARK_CARD, padx=12, pady=6)
        self.conn_frame.pack(side="right")
        
        self.conn_dot = tk.Label(self.conn_frame, text="●", font=("Segoe UI", 12),
                                bg=DARK_CARD, fg=DARK_ERROR)
        self.conn_dot.pack(side="left")
        
        self.conn_label = tk.Label(self.conn_frame, text="Disconnected",
                                  font=("Segoe UI", 10), bg=DARK_CARD, fg=DARK_MUTED)
        self.conn_label.pack(side="left", padx=(6, 0))
        
        # ===== CARDS ROW =====
        cards = tk.Frame(main, bg=DARK_BG)
        cards.pack(fill="x", pady=(0, 15))
        cards.columnconfigure(0, weight=1)
        cards.columnconfigure(1, weight=1)
        cards.columnconfigure(2, weight=1)
        
        self._make_card(cards, 0, "🌐 Melissa", "Connecting...", "melissa_val", "melissa_dot")
        self._make_card(cards, 1, "🔌 COM Ports", "0 found", "ports_val", "ports_dot")
        self._make_card(cards, 2, "📟 Arduino", "Not detected", "arduino_val", "arduino_dot")
        
        # ===== PORT SELECTION SECTION =====
        port_section = self._make_section(main, "COM Port Selection")
        
        port_row = tk.Frame(port_section, bg=DARK_CARD)
        port_row.pack(fill="x", pady=(10, 10))
        
        tk.Label(port_row, text="Port:", font=("Segoe UI", 10), bg=DARK_CARD, fg=DARK_TEXT).pack(side="left")
        
        self.port_var = tk.StringVar(value="Select port...")
        self.port_combo = ttk.Combobox(port_row, textvariable=self.port_var,
                                       values=["Scanning..."], state="readonly", width=20,
                                       font=("Segoe UI", 10))
        self.port_combo.pack(side="left", padx=(8, 0))
        self.port_combo.bind("<<ComboboxSelected>>", self._on_port_selected)
        
        tk.Label(port_row, text="Manual:", font=("Segoe UI", 10), bg=DARK_CARD, fg=DARK_MUTED).pack(side="left", padx=(20, 0))
        self.manual_entry = tk.Entry(port_row, width=12, font=("Segoe UI", 10),
                                    bg=DARK_BG, fg=DARK_TEXT, insertbackground=DARK_TEXT,
                                    relief="flat", bd=0)
        self.manual_entry.pack(side="left", padx=(8, 0))
        self.manual_entry.insert(0, "COM3")
        
        ttk.Button(port_row, text="🔄 Scan", command=self._refresh_ports, width=8).pack(side="left", padx=(15, 0))
        
        # ===== BOARD SELECTION SECTION =====
        board_section = self._make_section(main, "Board Configuration")
        
        board_row = tk.Frame(board_section, bg=DARK_CARD)
        board_row.pack(fill="x", pady=(10, 10))
        
        tk.Label(board_row, text="Board Type:", font=("Segoe UI", 10), bg=DARK_CARD, fg=DARK_TEXT).pack(side="left")
        
        self.board_var = tk.StringVar(value="uno")
        board_combo = ttk.Combobox(board_row, textvariable=self.board_var,
                                    values=["uno", "mega", "nano", "nano_old", "leonardo", "micro",
                                           "mini", "pro_mini", "due", "esp32", "esp8266"],
                                    state="readonly", width=15, font=("Segoe UI", 10))
        board_combo.pack(side="left", padx=(8, 0))
        
        ttk.Button(board_row, text="🔍 Identify", command=self._identify_board, width=10).pack(side="left", padx=(15, 0))
        
        # ===== ACTION BUTTONS =====
        actions = tk.Frame(main, bg=DARK_BG)
        actions.pack(fill="x", pady=(0, 15))
        
        btn_style = {"height": 2, "width": 18, "font": ("Segoe UI", 10, "bold")}
        
        self.connect_btn = tk.Button(actions, text="🔗 Connect to Melissa",
                                     bg=DARK_ACCENT, fg="white", relief="flat",
                                     cursor="hand2", **btn_style,
                                     command=self._toggle_connection)
        self.connect_btn.pack(side="left", padx=(0, 10))
        
        tk.Button(actions, text="⚡ Flash Firmware",
                 bg=DARK_SUCCESS, fg="white", relief="flat",
                 cursor="hand2", **btn_style,
                 command=self._flash_dialog).pack(side="left", padx=(0, 10))
        
        tk.Button(actions, text="🗑 Clear Logs",
                 bg=DARK_CARD, fg=DARK_TEXT, relief="flat",
                 cursor="hand2", **btn_style,
                 command=self._clear_logs).pack(side="left")
        
        # ===== LOG WINDOW =====
        log_section = self._make_section(main, "Activity Log")
        
        self.log_text = tk.Text(log_section, height=12, wrap="word",
                                font=("Cascadia Code", 9), bg=DARK_BG, fg=DARK_TEXT,
                                insertbackground=DARK_TEXT, relief="flat", bd=0,
                                padx=10, pady=10, state="disabled")
        self.log_text.pack(fill="both", expand=True)
        
        self.log_text.tag_config("INFO", foreground=DARK_TEXT)
        self.log_text.tag_config("SUCCESS", foreground=DARK_SUCCESS)
        self.log_text.tag_config("WARNING", foreground=DARK_WARNING)
        self.log_text.tag_config("ERROR", foreground=DARK_ERROR)
        self.log_text.tag_config("SYSTEM", foreground=DARK_ACCENT)
        self.log_text.tag_config("MELISSA", foreground="#60a5fa")
        
        # ===== STATUS BAR =====
        self.status_bar = tk.Label(main, text="Ready",
                                   font=("Segoe UI", 9), bg=DARK_CARD, fg=DARK_MUTED,
                                   anchor="w", padx=10, pady=6)
        self.status_bar.pack(fill="x", pady=(10, 0), ipady=2)
        
        self._log("SYSTEM", f"ArduinoBridge GUI v{VERSION} initialized")
        self._log("SYSTEM", f"Gateway: {OPENCLAW_WS}")
    
    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=DARK_BG, background=DARK_BG,
                       foreground=DARK_TEXT, bordercolor=DARK_BORDER)
        style.map("TCombobox", fieldbackground=[("readonly", DARK_BG)],
                  selectbackground=[("readonly", DARK_ACCENT)],
                  selectforeground=[("readonly", "white")])
    
    def _make_card(self, parent, col, title, initial, val_key, dot_key):
        card = tk.Frame(parent, bg=DARK_CARD, padx=15, pady=12,
                        highlightbackground=DARK_BORDER, highlightthickness=1)
        card.grid(row=0, column=col, padx=(0, 10) if col < 2 else (0, 0), sticky="ew")
        
        tk.Label(card, text=title, font=("Segoe UI", 9), bg=DARK_CARD,
                fg=DARK_MUTED).pack(anchor="w")
        
        value_frame = tk.Frame(card, bg=DARK_CARD)
        value_frame.pack(anchor="w", pady=(5, 0))
        
        dot = tk.Label(value_frame, text="●", font=("Segoe UI", 10),
                      bg=DARK_CARD, fg=DARK_ERROR)
        dot.pack(side="left")
        
        val = tk.Label(value_frame, text=initial, font=("Segoe UI", 11, "bold"),
                      bg=DARK_CARD, fg=DARK_TEXT)
        val.pack(side="left", padx=(6, 0))
        
        setattr(self, dot_key, dot)
        setattr(self, val_key, val)
        
        return card
    
    def _make_section(self, parent, title):
        section = tk.Frame(parent, bg=DARK_BG)
        section.pack(fill="x", pady=(0, 10))
        
        tk.Label(section, text=title, font=("Segoe UI", 11, "bold"),
                bg=DARK_BG, fg=DARK_TEXT).pack(anchor="w")
        
        container = tk.Frame(section, bg=DARK_CARD, padx=15, pady=8)
        container.pack(fill="x", pady=(8, 0), ipady=4)
        
        return container
    
    def _log(self, level, message):
        timestamp = time.strftime("%H:%M:%S")
        line = f"[{timestamp}] [{level}] {message}\n"
        
        self.log_text.config(state="normal")
        self.log_text.insert("end", line, level)
        self.log_text.see("end")
        self.log_text.config(state="disabled")
        
        getattr(logger, level.lower(), logger.info)(message)
    
    def _status(self, message):
        self.status_bar.config(text=message)
    
    def _set_dot(self, dot_key, val_key, color, text):
        dot = getattr(self, dot_key)
        val = getattr(self, val_key)
        dot.config(fg=color)
        val.config(text=text)
    
    def _after(self, ms, func):
        self.root.after(ms, func)
    
    def _connect_to_melissa(self):
        self._log("SYSTEM", "Starting connection to Melissa...")
        self.melissa.connect()
    
    def _toggle_connection(self):
        if self.melissa.connected:
            self.melissa.disconnect()
            self.connect_btn.config(text="🔗 Connect to Melissa", bg=DARK_ACCENT)
        else:
            self.melissa.connect()
            self.connect_btn.config(text="⟳ Connecting...", bg=DARK_WARNING)
    
    def _on_connected(self):
        self.conn_dot.config(fg=DARK_SUCCESS)
        self.conn_label.config(text="Connected", fg=DARK_SUCCESS)
        self._set_dot("melissa_dot", "melissa_val", DARK_SUCCESS, "Connected")
        self.connect_btn.config(text="🔌 Disconnect", bg=DARK_ERROR)
        self.melissa.send_event("arduino.connected", {"status": "online"})
    
    def _on_disconnected(self):
        self.conn_dot.config(fg=DARK_ERROR)
        self.conn_label.config(text="Disconnected", fg=DARK_MUTED)
        self._set_dot("melissa_dot", "melissa_val", DARK_ERROR, "Disconnected")
        self.connect_btn.config(text="🔗 Reconnect", bg=DARK_ACCENT)
    
    def _refresh_ports(self):
        if not SERIAL_AVAILABLE:
            self._set_dot("ports_dot", "ports_val", DARK_WARNING, "No pyserial")
            return
        
        self._log("INFO", "Scanning COM ports...")
        ports = []
        try:
            for p in serial.tools.list_ports.comports():
                ports.append(f"{p.device} - {p.description or 'Unknown'}")
        except Exception as e:
            self._log("ERROR", f"Port scan failed: {e}")
        
        if ports:
            self.port_combo.config(values=ports)
            self._set_dot("ports_dot", "ports_val", DARK_SUCCESS, f"{len(ports)} port(s)")
            self._log("SUCCESS", f"Found {len(ports)} port(s)")
        else:
            self.port_combo.config(values=["No ports found"])
            self._set_dot("ports_dot", "ports_val", DARK_WARNING, "No ports")
    
    def _on_port_selected(self, event):
        selection = self.port_var.get()
        if selection and " - " in selection:
            port = selection.split(" - ")[0]
            self._log("INFO", f"Port selected: {port}")
    
    def _identify_board(self):
        port = self.manual_entry.get().strip()
        if not port:
            messagebox.showwarning("No Port", "Enter a port first")
            return
        
        self._log("INFO", f"Identifying board on {port}...")
        
        def identify():
            try:
                import serial
                with serial.Serial(port, 115200, timeout=1) as ser:
                    ser.write(b"\r\n")
                    time.sleep(0.3)
                    response = ""
                    if ser.in_waiting:
                        response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                    
                    board = "unknown"
                    if "Mega" in response: board = "mega"
                    elif "Uno" in response: board = "uno"
                    elif "Nano" in response: board = "nano"
                    elif "Leonardo" in response: board = "leonardo"
                    
                    self.board_var.set(board)
                    self._set_dot("arduino_dot", "arduino_val", DARK_SUCCESS, board.upper())
                    self._log("SUCCESS", f"Board: {board}")
                    
                    # Notify Melissa
                    self.melissa.send_event("arduino.identified", {
                        "port": port, "board": board, "response": response[:100]
                    })
                    
            except Exception as e:
                self._log("ERROR", f"Identify failed: {e}")
                self._set_dot("arduino_dot", "arduino_val", DARK_ERROR, "Error")
        
        threading.Thread(target=identify, daemon=True).start()
    
    def _do_scan(self):
        """Perform port scan, return results"""
        if not SERIAL_AVAILABLE:
            return []
        
        ports = []
        try:
            for p in serial.tools.list_ports.comports():
                ports.append({"port": p.device, "description": p.description})
        except:
            pass
        return ports
    
    def _do_identify(self, port):
        """Identify board on port"""
        if not port or not SERIAL_AVAILABLE:
            return {"success": False, "error": "No port or pyserial unavailable"}
        
        try:
            import serial
            with serial.Serial(port, 115200, timeout=1) as ser:
                ser.write(b"\r\n")
                time.sleep(0.3)
                response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                
                board = "unknown"
                if "Mega" in response: board = "mega"
                elif "Uno" in response: board = "uno"
                elif "Nano" in response: board = "nano"
                
                return {"success": True, "port": port, "board": board, "response": response[:100]}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_flash_command(self, params):
        """Handle flash command from Melissa"""
        port = params.get("port", self.manual_entry.get().strip())
        board = params.get("board", self.board_var.get())
        hex_data = params.get("hex")
        
        if not port:
            self._log("ERROR", "Flash: No port specified!")
            return
        
        self._log("INFO", f"FLASH REQUEST from Melissa: {board} on {port}")
        
        if hex_data:
            self._flash_hex(port, board, hex_data)
        else:
            self._log("WARNING", "Flash: No hex data provided")
    
    def _flash_hex(self, port, board, hex_data):
        """Flash hex data to Arduino"""
        self._log("INFO", f"Flashing {len(hex_data)} bytes to {port}...")
        
        def flash():
            try:
                # Write hex to temp file
                hex_file = os.path.join(os.environ.get("TEMP", "/tmp"), "flash.hex")
                with open(hex_file, "w") as f:
                    f.write(hex_data)
                
                # Use avrdude
                import subprocess
                
                # Board-specific settings
                board_config = {
                    "uno": ("m328p", "115200"),
                    "mega": ("m2560", "115200"),
                    "nano": ("m328p", "57600"),
                    "leonardo": ("m32u4", "115200"),
                }
                
                mcu, speed = board_config.get(board, ("m328p", "115200"))
                
                cmd = [
                    "avrdude", "-v",
                    "-p", mcu,
                    "-c", "arduino",
                    "-P", port,
                    "-b", speed,
                    "-D", "-U", f"flash:w:{hex_file}:i"
                ]
                
                self._log("SYSTEM", f"Running: {' '.join(cmd[:5])}...")
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0:
                    self._log("SUCCESS", "✓ Flash successful!")
                    self.melissa.send_event("arduino.flash_complete", {
                        "success": True, "port": port, "board": board
                    })
                else:
                    self._log("ERROR", f"Flash failed: {result.stderr}")
                    self.melissa.send_event("arduino.flash_complete", {
                        "success": False, "port": port, "board": board, "error": result.stderr
                    })
                
                # Cleanup
                try:
                    os.unlink(hex_file)
                except:
                    pass
                    
            except Exception as e:
                self._log("ERROR", f"Flash error: {e}")
                self.melissa.send_event("arduino.flash_complete", {
                    "success": False, "error": str(e)
                })
        
        threading.Thread(target=flash, daemon=True).start()
    
    def _flash_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Flash Firmware")
        dialog.configure(bg=DARK_BG)
        dialog.geometry("400x300")
        dialog.resizable(False, False)
        
        tk.Label(dialog, text="Flash Firmware", font=("Segoe UI", 14, "bold"),
                bg=DARK_BG, fg=DARK_TEXT).pack(pady=15)
        
        info = f"Board: {self.board_var.get()}\nPort: {self.manual_entry.get()}\n\nMelissa can send firmware to flash."
        
        tk.Label(dialog, text=info, font=("Segoe UI", 10),
                bg=DARK_BG, fg=DARK_MUTED, justify="left").pack(pady=10)
        
        tk.Button(dialog, text="✓ Close", bg=DARK_ACCENT, fg="white", relief="flat",
                 font=("Segoe UI", 10), cursor="hand2",
                 command=dialog.destroy).pack(pady=20)
    
    def _clear_logs(self):
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, "end")
        self.log_text.config(state="disabled")
        self._log("SYSTEM", "Logs cleared")


def main():
    root = tk.Tk()
    app = ModernGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

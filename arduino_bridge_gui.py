#!/usr/bin/env python3
"""
ArduinoBridge GUI - Modern Dark Theme Desktop App
Connects to Melissa/OpenClaw Gateway automatically
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

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("arduino-bridge-gui")

VERSION = "0.2.0"

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
DARK_ACCENT = "#7c3aed"  # Purple accent
DARK_SUCCESS = "#10b981"
DARK_ERROR = "#ef4444"
DARK_WARNING = "#f59e0b"
DARK_TEXT = "#e2e8f0"
DARK_MUTED = "#94a3b8"
DARK_BORDER = "#3f3f5a"

class ModernGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"🔌 ArduinoBridge GUI v{VERSION}")
        self.root.configure(bg=DARK_BG)
        self.root.geometry("800x700")
        self.root.minsize(700, 600)
        
        # State
        self.connected = False
        self.serial_connected = False
        self.refresh_timer = None
        
        # Build UI
        self._build_ui()
        
        # Auto-connect to OpenClaw
        self._after(1000, self._connect_to_openclaw)
        self._after(2000, self._refresh_ports)
    
    def _build_ui(self):
        # Custom styles
        self._setup_styles()
        
        # Main container with padding
        main = tk.Frame(self.root, bg=DARK_BG, padx=20, pady=20)
        main.pack(fill="both", expand=True)
        
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
        
        # Card 1: Gateway Status
        self._make_card(cards, 0, "🌐 Gateway", "Unknown", "gateway_val", "gateway_dot")
        
        # Card 2: COM Ports
        self._make_card(cards, 1, "🔌 COM Ports", "0 found", "ports_val", "ports_dot")
        
        # Card 3: Arduino Status
        self._make_card(cards, 2, "📟 Arduino", "Not detected", "arduino_val", "arduino_dot")
        
        # ===== PORT SELECTION SECTION =====
        port_section = self._make_section(main, "COM Port Selection")
        
        port_row = tk.Frame(port_section, bg=DARK_CARD)
        port_row.pack(fill="x", pady=(10, 10))
        
        # Port dropdown
        tk.Label(port_row, text="Port:", font=("Segoe UI", 10), bg=DARK_CARD, fg=DARK_TEXT).pack(side="left")
        
        self.port_var = tk.StringVar(value="Select port...")
        self.port_combo = ttk.Combobox(port_row, textvariable=self.port_var,
                                       values=["Scanning..."], state="readonly", width=20,
                                       font=("Segoe UI", 10))
        self.port_combo.pack(side="left", padx=(8, 0))
        self.port_combo.bind("<<ComboboxSelected>>", self._on_port_selected)
        
        # Manual port entry
        tk.Label(port_row, text="Manual:", font=("Segoe UI", 10), bg=DARK_CARD, fg=DARK_MUTED).pack(side="left", padx=(20, 0))
        self.manual_entry = tk.Entry(port_row, width=12, font=("Segoe UI", 10),
                                    bg=DARK_BG, fg=DARK_TEXT, insertbackground=DARK_TEXT,
                                    relief="flat", bd=0)
        self.manual_entry.pack(side="left", padx=(8, 0))
        self.manual_entry.insert(0, "COM3")
        
        ttk.Button(port_row, text="🔄 Scan", command=self._refresh_ports,
                   width=8).pack(side="left", padx=(15, 0))
        
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
        
        ttk.Button(board_row, text="🔍 Identify", command=self._identify_board,
                   width=10).pack(side="left", padx=(15, 0))
        
        # ===== ACTION BUTTONS =====
        actions = tk.Frame(main, bg=DARK_BG)
        actions.pack(fill="x", pady=(0, 15))
        
        btn_style = {"height": 2, "width": 18, "font": ("Segoe UI", 10, "bold")}
        
        self.connect_btn = tk.Button(actions, text="▶ Connect to Melissa",
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
        
        # Configure text tags
        self.log_text.tag_config("INFO", foreground=DARK_TEXT)
        self.log_text.tag_config("SUCCESS", foreground=DARK_SUCCESS)
        self.log_text.tag_config("WARNING", foreground=DARK_WARNING)
        self.log_text.tag_config("ERROR", foreground=DARK_ERROR)
        self.log_text.tag_config("SYSTEM", foreground=DARK_ACCENT)
        self.log_text.tag_config("MELISSA", foreground="#60a5fa")  # Blue
        
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
        
        # Combobox
        style.configure("TCombobox", fieldbackground=DARK_BG, background=DARK_BG,
                       foreground=DARK_TEXT, bordercolor=DARK_BORDER)
        style.map("TCombobox", fieldbackground=[("readonly", DARK_BG)],
                  selectbackground=[("readonly", DARK_ACCENT)],
                  selectforeground=[("readonly", "white")])
        
        # Buttons
        style.configure("TButton", background=DARK_ACCENT, foreground="white",
                       bordercolor=DARK_ACCENT, relief="flat")
        style.map("TButton", background=[("active", DARK_ACCENT)])
    
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
    
    def _refresh_ports(self):
        if not SERIAL_AVAILABLE:
            self._set_dot("ports_dot", "ports_val", DARK_WARNING, "pyserial not available")
            self._log("WARNING", "pyserial not installed - cannot scan ports")
            return
        
        self._log("INFO", "Scanning COM ports...")
        ports = []
        try:
            for p in serial.tools.list_ports.comports():
                ports.append(f"{p.device} - {p.description or 'Unknown'}")
                self._log("SYSTEM", f"Found: {p.device}")
        except Exception as e:
            self._log("ERROR", f"Port scan failed: {e}")
        
        if ports:
            self.port_combo.config(values=ports)
            self._set_dot("ports_dot", "ports_val", DARK_SUCCESS, f"{len(ports)} port(s)")
            self._log("SUCCESS", f"Found {len(ports)} COM port(s)")
        else:
            self.port_combo.config(values=["No ports found"])
            self._set_dot("ports_dot", "ports_val", DARK_WARNING, "No ports")
            self._log("WARNING", "No COM ports found")
    
    def _on_port_selected(self, event):
        selection = self.port_var.get()
        if selection and selection != "No ports found" and " - " in selection:
            port = selection.split(" - ")[0]
            self._log("INFO", f"Port selected: {port}")
            self._status(f"Selected: {port}")
    
    def _identify_board(self):
        port = self.manual_entry.get().strip() or self.port_var.get().split(" - ")[0]
        if not port or "No ports" in port:
            messagebox.showwarning("No Port", "Select a port first")
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
                    if "Mega" in response or "mega" in response:
                        board = "mega"
                    elif "Uno" in response or "uno" in response:
                        board = "uno"
                    elif "Nano" in response or "nano" in response:
                        board = "nano"
                    elif "Leonardo" in response:
                        board = "leonardo"
                    
                    if board != "unknown":
                        self.board_var.set(board)
                        self._set_dot("arduino_dot", "arduino_val", DARK_SUCCESS, board.upper())
                        self._log("SUCCESS", f"Board detected: {board}")
                    else:
                        self._set_dot("arduino_dot", "arduino_val", DARK_WARNING, "Unknown")
                        self._log("WARNING", f"Could not identify board. Response: {response[:50]}")
                        
            except Exception as e:
                self._log("ERROR", f"Identify failed: {e}")
                self._set_dot("arduino_dot", "arduino_val", DARK_ERROR, "Error")
        
        threading.Thread(target=identify, daemon=True).start()
    
    def _connect_to_openclaw(self):
        self._log("SYSTEM", f"Connecting to OpenClaw gateway...")
        
        try:
            req = urllib.request.Request(f"{OPENCLAW_HTTP}/health")
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    self._set_dot("gateway_dot", "gateway_val", DARK_SUCCESS, "Connected")
                    self._log("SUCCESS", f"OpenClaw gateway reachable at {OPENCLAW_HTTP}")
                    self.connected = True
                    return
        except Exception as e:
            self._log("WARNING", f"Cannot reach OpenClaw: {e}")
        
        self._set_dot("gateway_dot", "gateway_val", DARK_ERROR, "Offline")
        self._log("ERROR", f"OpenClaw gateway not reachable at {OPENCLAW_HTTP}")
        
        # Retry after 5 seconds
        self._after(5000, self._connect_to_openclaw)
    
    def _toggle_connection(self):
        if self.connected:
            self._log("SYSTEM", "Disconnect requested (not implemented yet)")
            self.connected = False
            self.connect_btn.config(text="▶ Connect", bg=DARK_ACCENT)
        else:
            self.connect_btn.config(text="⟳ Connecting...", bg=DARK_WARNING)
            self._connect_to_openclaw()
    
    def _flash_dialog(self):
        port = self.manual_entry.get().strip()
        board = self.board_var.get()
        
        self._log("INFO", f"Flash requested: {board} on {port}")
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Flash Firmware")
        dialog.configure(bg=DARK_BG)
        dialog.geometry("400x300")
        dialog.resizable(False, False)
        
        tk.Label(dialog, text="Flash Firmware", font=("Segoe UI", 14, "bold"),
                bg=DARK_BG, fg=DARK_TEXT).pack(pady=15)
        
        info = f"Board: {board}\nPort: {port}\n\nSend the firmware hex to Melissa\nand she will flash it for you."
        
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
    
    # Set window icon (if available)
    try:
        root.iconbitmap("icon.ico")
    except:
        pass
    
    app = ModernGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

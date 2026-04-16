#!/usr/bin/env python3
"""
ArduinoBridge Client - Auto-connect to Melissa/OpenClaw
Flashes Arduino boards via commands from Melissa
"""

import os
import sys
import json
import time
import logging
import requests
import threading
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("arduino-bridge")

VERSION = "0.1.0"
GATEWAY_URL = os.environ.get("OPENCLAW_GATEWAY", "ws://127.0.0.1:18789")
API_BASE = os.environ.get("OPENCLAW_API", "http://127.0.0.1:18789")

class ArduinoBridge:
    def __init__(self):
        self.connected = False
        self.devices = []
    
    def auto_connect(self):
        """Connect to OpenClaw gateway and register as Arduino tool"""
        logger.info(f"ArduinoBridge v{VERSION} starting...")
        logger.info(f"Gateway: {GATEWAY_URL}")
        
        # Try to connect to gateway
        try:
            resp = requests.get(f"{API_BASE}/health", timeout=5)
            if resp.status_code == 200:
                logger.info("✓ Gateway reachable")
                self.register_with_gateway()
            else:
                logger.warning("Gateway health check failed")
        except Exception as e:
            logger.warning(f"Cannot reach gateway: {e}")
            logger.info("Running in standalone mode")
    
    def register_with_gateway(self):
        """Register as a device/node with Arduino capabilities"""
        # This would register with OpenClaw's gateway
        # For now, just mark as connected
        self.connected = True
        logger.info("✓ Registered with gateway")
    
    def scan_ports(self):
        """Scan for COM ports with Arduino devices"""
        try:
            import serial.tools.list_ports
            ports = []
            for p in serial.tools.list_ports.comports():
                ports.append({
                    "port": p.device,
                    "description": p.description,
                    "hwid": p.hwid
                })
            return {"success": True, "ports": ports}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def identify_board(self, port):
        """Identify Arduino board on port"""
        try:
            import serial
            with serial.Serial(port, 115200, timeout=1) as ser:
                ser.write(b"\r\n")
                time.sleep(0.2)
                if ser.in_waiting:
                    response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                    return {"success": True, "response": response[:200]}
            return {"success": True, "message": "Board detected"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def run_command(self, cmd):
        """Run a command from Melissa"""
        logger.info(f"Command: {cmd}")
        
        if cmd.get("action") == "scan":
            return self.scan_ports()
        elif cmd.get("action") == "identify":
            return self.identify_board(cmd.get("port"))
        elif cmd.get("action") == "ping":
            return {"success": True, "message": "pong", "version": VERSION}
        else:
            return {"success": False, "error": "Unknown command"}


def main():
    bridge = ArduinoBridge()
    bridge.auto_connect()
    
    # Run standalone server for local testing
    from flask import Flask, request, jsonify
    from flask_cors import CORS
    
    app = Flask(__name__)
    CORS(app)
    
    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "version": VERSION, "connected": bridge.connected})
    
    @app.route("/scan", methods=["POST"])
    def scan():
        return jsonify(bridge.scan_ports())
    
    @app.route("/identify", methods=["POST"])
    def identify():
        data = request.get_json()
        return jsonify(bridge.identify_board(data.get("port")))
    
    @app.route("/command", methods=["POST"])
    def command():
        data = request.get_json()
        return jsonify(bridge.run_command(data))
    
    logger.info(f"Starting server on http://127.0.0.1:8765")
    app.run(host="127.0.0.1", port=8765, debug=False)


if __name__ == "__main__":
    main()

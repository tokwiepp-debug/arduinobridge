#!/usr/bin/env python3
"""ArduinoBridge Client - Minimal Version for Testing"""
import os, sys, logging, time
from flask import Flask, request, jsonify
from flask_cors import CORS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("arduino-bridge")

VERSION = "0.1.0"

app = Flask(__name__)
CORS(app)

@app.route("/health")
def health():
    return jsonify({"status": "ok", "version": VERSION})

@app.route("/ports")
def ports():
    # Return empty ports for now
    import serial.tools.list_ports
    ports = []
    try:
        for p in serial.tools.list_ports.comports():
            ports.append({"port": p.device, "description": p.description})
    except Exception as e:
        logger.warning(f"Port scan failed: {e}")
    return jsonify({"ports": ports, "count": len(ports)})

@app.route("/identify")
def identify():
    port = request.args.get("port")
    return jsonify({"port": port, "board": "unknown", "confidence": 0})

@app.route("/command", methods=["POST"])
def command():
    data = request.get_json or {}
    return jsonify({"success": True, "action": data.get("action", "none")})

if __name__ == "__main__":
    logger.info(f"ArduinoBridge v{VERSION} starting on http://127.0.0.1:8765")
    app.run(host="127.0.0.1", port=8765, debug=False)

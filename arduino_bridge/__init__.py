#!/usr/bin/env python3
"""ArduinoBridge Server - Same as test-flask that worked"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

VERSION = "0.1.0"

@app.route("/health")
def health():
    return jsonify({"status": "ok", "version": VERSION, "service": "arduino-bridge"})

@app.route("/ports")
def ports():
    try:
        import serial.tools.list_ports
        port_list = []
        for p in serial.tools.list_ports.comports():
            port_list.append({"port": p.device, "description": p.description})
        return jsonify({"ports": port_list, "count": len(port_list)})
    except Exception as e:
        return jsonify({"ports": [], "count": 0, "error": str(e)})

@app.route("/identify")
def identify():
    port = request.args.get("port", "")
    return jsonify({"port": port, "board": "unknown", "confidence": 0})

@app.route("/command", methods=["POST"])
def command():
    return jsonify({"success": True, "message": "arduino-bridge ready"})

if __name__ == "__main__":
    logger.info(f"ArduinoBridge v{VERSION} starting...")
    logger.info("Server on http://127.0.0.1:8765")
    app.run(host="127.0.0.1", port=8765, debug=False)

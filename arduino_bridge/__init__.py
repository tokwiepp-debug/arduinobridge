#!/usr/bin/env python3
"""ArduinoBridge Server - NO native dependencies"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

@app.route("/health")
def health():
    return jsonify({"status": "ok", "version": "0.1.0", "service": "arduino-bridge"})

@app.route("/ports")
def ports():
    return jsonify({"ports": [], "count": 0, "message": "pyserial not available in this build"})

@app.route("/identify")
def identify():
    return jsonify({"port": request.args.get("port", ""), "board": "unknown", "confidence": 0})

@app.route("/command", methods=["POST"])
def command():
    return jsonify({"success": True, "message": "ready"})

if __name__ == "__main__":
    logger.info("ArduinoBridge v0.1.0 starting on http://127.0.0.1:8765")
    app.run(host="127.0.0.1", port=8765, debug=False)

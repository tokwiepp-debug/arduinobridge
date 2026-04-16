#!/usr/bin/env python3
"""
ArduinoBridge Server - Standalone Version
Flask REST API for Arduino programming
"""

import os
import sys
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Import our modules
try:
    from port_scanner import list_ports, filter_arduino_ports
    from board_identifier import identify_board
    from flash_manager import FlashManager
    logger.info("Modules loaded successfully")
except ImportError as e:
    logger.error(f"Import error: {e}")
    # Fallback - try from parent
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from arduino_bridge.port_scanner import list_ports, filter_arduino_ports
        from arduino_bridge.board_identifier import identify_board
        from arduino_bridge.flash_manager import FlashManager
        logger.info("Modules loaded from arduino_bridge")
    except ImportError as e2:
        logger.error(f"Also failed: {e2}")

fm = FlashManager()

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "version": "0.1.0"})

@app.route("/ports", methods=["GET"])
def get_ports():
    ports = list_ports()
    arduino_ports = filter_arduino_ports(ports)
    return jsonify({
        "all_ports": ports,
        "arduino_ports": arduino_ports,
        "count": len(ports),
        "arduino_count": len(arduino_ports)
    })

@app.route("/board", methods=["GET"])
def get_board():
    port = request.args.get("port")
    if not port:
        return jsonify({"error": "Missing 'port' parameter"}), 400
    try:
        board = identify_board(port)
        return jsonify({
            "port": board.port,
            "board_name": board.board_name,
            "board_type": board.board_type,
            "confidence": board.confidence
        })
    except Exception as e:
        logger.exception(f"Error identifying board on {port}")
        return jsonify({"error": str(e)}), 500

@app.route("/flash", methods=["POST"])
def flash():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400
    
    port = data.get("port")
    board_type = data.get("board_type")
    firmware_path = data.get("firmware_path")
    firmware_hex = data.get("firmware_hex")
    
    if not port or not board_type:
        return jsonify({"error": "Missing 'port' or 'board_type'"}), 400
    
    result = fm.flash(port=port, board_type=board_type, firmware_path=firmware_path, firmware_hex=firmware_hex)
    return jsonify({
        "success": result.success,
        "message": result.message,
        "duration_seconds": result.duration_seconds
    })

if __name__ == "__main__":
    logger.info("Starting ArduinoBridge server on http://127.0.0.1:8765")
    app.run(host="127.0.0.1", port=8765, debug=False)

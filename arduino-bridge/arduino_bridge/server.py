"""
ArduinoBridge REST API Server
Provides HTTP endpoints for OpenClaw integration
"""

import os
import sys
import logging
import argparse
from flask import Flask, request, jsonify
from flask_cors import CORS

from .port_scanner import list_ports, filter_arduino_ports
from .board_identifier import identify_board, BoardInfo
from .flash_manager import FlashManager
from .plugin_system import PluginManager

logger = logging.getLogger(__name__)


def create_app(plugin_manager: PluginManager = None, flash_manager: FlashManager = None) -> Flask:
    """Create and configure the Flask app"""
    
    app = Flask(__name__)
    CORS(app)  # Allow cross-origin requests for local apps
    
    pm = plugin_manager or PluginManager()
    fm = flash_manager or FlashManager()
    
    # Store managers on app
    app.plugin_manager = pm
    app.flash_manager = fm
    
    # Progress callback for flash operations
    def flash_progress(msg: str, pct: float):
        # Could emit to WebSocket here if needed
        logger.debug(f"Flash progress: {msg} ({pct}%)")
    
    fm.set_progress_callback(flash_progress)
    
    # === API Routes ===
    
    @app.route("/health", methods=["GET"])
    def health():
        """Health check endpoint"""
        return jsonify({"status": "ok", "version": "0.1.0"})
    
    @app.route("/ports", methods=["GET"])
    def get_ports():
        """List all available serial ports"""
        all_ports = list_ports()
        arduino_ports = filter_arduino_ports(all_ports)
        
        return jsonify({
            "all_ports": all_ports,
            "arduino_ports": arduino_ports,
            "count": len(all_ports),
            "arduino_count": len(arduino_ports)
        })
    
    @app.route("/ports/arduino", methods=["GET"])
    def get_arduino_ports():
        """List only Arduino-detected ports"""
        ports = filter_arduino_ports(list_ports())
        return jsonify({"ports": ports, "count": len(ports)})
    
    @app.route("/board", methods=["GET"])
    def get_board():
        """Identify board on a specific port"""
        port = request.args.get("port")
        if not port:
            return jsonify({"error": "Missing 'port' parameter"}), 400
        
        try:
            board: BoardInfo = identify_board(port)
            
            # Notify plugins
            pm.notify_board_identified({
                "port": board.port,
                "board_name": board.board_name,
                "board_type": board.board_type,
                "confidence": board.confidence,
                "detection_method": board.detection_method
            })
            
            return jsonify({
                "port": board.port,
                "board_name": board.board_name,
                "board_type": board.board_type,
                "vid": board.vid,
                "pid": board.pid,
                "serial_number": board.serial_number,
                "firmware_version": board.firmware_version,
                "confidence": board.confidence,
                "detection_method": board.detection_method
            })
        except Exception as e:
            logger.exception(f"Error identifying board on {port}")
            return jsonify({"error": str(e)}), 500
    
    @app.route("/identify-all", methods=["POST"])
    def identify_all():
        """Scan all ports and identify any Arduino boards"""
        ports = filter_arduino_ports(list_ports())
        results = []
        
        for port_info in ports:
            try:
                board = identify_board(port_info["port"])
                results.append({
                    "port": board.port,
                    "board_name": board.board_name,
                    "board_type": board.board_type,
                    "confidence": board.confidence
                })
            except Exception as e:
                results.append({
                    "port": port_info["port"],
                    "error": str(e)
                })
        
        return jsonify({"boards": results})
    
    @app.route("/flash", methods=["POST"])
    def flash():
        """
        Flash firmware to a board.
        
        JSON body:
        {
            "port": "COM3",
            "board_type": "uno",
            "firmware_path": "/path/to/firmware.hex",  // OR
            "firmware_hex": "010203...",  // hex string
            "verify": true
        }
        """
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400
        
        port = data.get("port")
        board_type = data.get("board_type")
        firmware_path = data.get("firmware_path")
        firmware_hex = data.get("firmware_hex")
        verify = data.get("verify", True)
        
        if not port:
            return jsonify({"error": "Missing 'port'"}), 400
        if not board_type:
            return jsonify({"error": "Missing 'board_type'"}), 400
        if not firmware_path and not firmware_hex:
            return jsonify({"error": "Missing 'firmware_path' or 'firmware_hex'"}), 400
        
        # Notify plugins flash is starting
        pm.notify_flash_start(port, board_type, firmware_path or "(hex data)")
        
        result = fm.flash(
            port=port,
            board_type=board_type,
            firmware_path=firmware_path,
            firmware_hex=firmware_hex,
            verify=verify
        )
        
        # Notify plugins flash complete
        pm.notify_flash_complete({
            "success": result.success,
            "message": result.message,
            "duration_seconds": result.duration_seconds,
            "port": result.port,
            "board_type": result.board_type,
            "method": result.method
        })
        
        return jsonify({
            "success": result.success,
            "message": result.message,
            "duration_seconds": result.duration_seconds,
            "board_type": result.board_type,
            "port": result.port,
            "method": result.method,
            "output": result.output
        })
    
    @app.route("/flash/status", methods=["GET"])
    def flash_status():
        """Check if flasher is available"""
        return jsonify({
            "avrdude": fm.avrdude_path is not None,
            "avrdude_path": fm.avrdude_path,
            "platformio": fm.platformio_path is not None,
            "esptool": fm.esptool_path is not None
        })
    
    # === Plugin Endpoints ===
    
    @app.route("/plugins", methods=["GET"])
    def get_plugins():
        """List all loaded plugins"""
        plugins = pm.list_plugins()
        return jsonify({
            "plugins": [
                {
                    "name": p.name,
                    "version": p.version,
                    "description": p.description,
                    "author": p.author
                }
                for p in plugins
            ],
            "count": len(plugins)
        })
    
    @app.route("/plugins/load", methods=["POST"])
    def load_plugin():
        """Load a plugin by name"""
        data = request.get_json()
        name = data.get("name") if data else None
        
        if not name:
            return jsonify({"error": "Missing 'name'"}), 400
        
        success = pm.load_plugin(name)
        return jsonify({"success": success, "plugin": name})
    
    @app.route("/plugins/unload", methods=["POST"])
    def unload_plugin():
        """Unload a plugin by name"""
        data = request.get_json()
        name = data.get("name") if data else None
        
        if not name:
            return jsonify({"error": "Missing 'name'"}), 400
        
        success = pm.unload_plugin(name)
        return jsonify({"success": success, "plugin": name})
    
    @app.route("/plugins/reload", methods=["POST"])
    def reload_plugin():
        """Reload a plugin"""
        data = request.get_json()
        name = data.get("name") if data else None
        
        if not name:
            return jsonify({"error": "Missing 'name'"}), 400
        
        success = pm.reload_plugin(name)
        return jsonify({"success": success, "plugin": name})
    
    @app.route("/plugins/scan", methods=["POST"])
    def scan_plugins():
        """Scan plugin directory for available plugins"""
        plugin_dir = pm.plugin_dir
        available = []
        
        if os.path.exists(plugin_dir):
            for filename in os.listdir(plugin_dir):
                if filename.endswith(".py") and not filename.startswith("_"):
                    name = filename[:-3]
                    available.append(name)
        
        return jsonify({
            "available": available,
            "loaded": list(pm.plugins.keys()),
            "plugin_dir": plugin_dir
        })
    
    return app


def run_server(host: str = "127.0.0.1", port: int = 8765, debug: bool = False):
    """Run the Flask server"""
    pm = PluginManager()
    pm.load_all_plugins()  # Auto-load plugins
    
    fm = FlashManager()
    
    app = create_app(pm, fm)
    
    logger.info(f"Starting ArduinoBridge server on {host}:{port}")
    logger.info(f"Plugin directory: {pm.plugin_dir}")
    logger.info(f"Avrdude: {fm.avrdude_path or 'not found'}")
    
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    parser = argparse.ArgumentParser(description="ArduinoBridge REST API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--load-plugins", action="store_true", default=True, help="Auto-load plugins")
    
    args = parser.parse_args()
    
    run_server(host=args.host, port=args.port, debug=args.debug)

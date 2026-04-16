#!/usr/bin/env python3
"""
ArduinoBridge CLI
Command-line interface for Arduino programming
"""

import os
import sys
import argparse
import logging
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arduino_bridge.port_scanner import list_ports, filter_arduino_ports
from arduino_bridge.board_identifier import identify_board
from arduino_bridge.flash_manager import FlashManager
from arduino_bridge.plugin_system import PluginManager
from arduino_bridge.server import create_app


def setup_logging(verbose: bool = False):
    """Configure logging"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )


def cmd_scan(args):
    """Scan for available ports"""
    ports = list_ports()
    
    if args.arduino_only:
        ports = filter_arduino_ports(ports)
        print(f"\n=== Arduino Ports ({len(ports)}) ===")
    else:
        print(f"\n=== All Ports ({len(ports)}) ===")
    
    if not ports:
        print("  No ports found")
        return
    
    for p in ports:
        arduino_marker = " [ARDUINO?]" if filter_arduino_ports([p]) else ""
        print(f"\n  Port:     {p['port']}")
        print(f"  Name:     {p.get('name', 'N/A')}")
        print(f"  Desc:     {p.get('description', 'N/A')}")
        print(f"  HWID:     {p.get('hwid', 'N/A')}")
        if p.get('usb_info'):
            print(f"  USB VID:  {p['usb_info'].get('vid', 'N/A')}")
            print(f"  USB PID:  {p['usb_info'].get('pid', 'N/A')}")
        if p.get('manufacturer'):
            print(f"  Maker:    {p['manufacturer']}")


def cmd_identify(args):
    """Identify board on a port"""
    if not args.port:
        print("Error: --port required")
        return 1
    
    print(f"Identifying board on {args.port}...")
    board = identify_board(args.port)
    
    print(f"\n  Port:             {board.port}")
    print(f"  Board Name:       {board.board_name}")
    print(f"  Board Type:       {board.board_type}")
    print(f"  Confidence:       {board.confidence:.0%}")
    print(f"  Detection:        {board.detection_method}")
    if board.vid:
        print(f"  VID:              {board.vid}")
    if board.pid:
        print(f"  PID:              {board.pid}")
    if board.serial_number:
        print(f"  Serial:           {board.serial_number}")
    
    return 0


def cmd_flash(args):
    """Flash firmware to a board"""
    if not args.port:
        print("Error: --port required")
        return 1
    if not args.board:
        print("Error: --board required")
        return 1
    if not args.file:
        print("Error: --file required")
        return 1
    
    if not os.path.exists(args.file):
        print(f"Error: File not found: {args.file}")
        return 1
    
    print(f"Flashing {args.file} to {args.port} ({args.board})...")
    
    fm = FlashManager()
    
    def progress(msg: str, pct: float):
        bar_len = 30
        filled = int(bar_len * pct / 100)
        bar = "=" * filled + "-" * (bar_len - filled)
        print(f"\r  [{bar}] {pct:5.1f}% {msg}", end="", flush=True)
    
    fm.set_progress_callback(progress)
    
    result = fm.flash(
        port=args.port,
        board_type=args.board,
        firmware_path=args.file,
        verify=not args.no_verify
    )
    
    print()  # Newline after progress bar
    
    if result.success:
        print(f"✓ Success! ({result.duration_seconds:.1f}s)")
        return 0
    else:
        print(f"✗ Failed: {result.message}")
        return 1


def cmd_server(args):
    """Start the REST API server"""
    from arduino_bridge.server import run_server
    run_server(host=args.host, port=args.port, debug=args.debug)


def cmd_plugins(args):
    """Manage plugins"""
    pm = PluginManager()
    
    if args.plugin_action == "list":
        plugins = pm.list_plugins()
        print(f"\n=== Loaded Plugins ({len(plugins)}) ===")
        if not plugins:
            print("  No plugins loaded")
        for p in plugins:
            print(f"  {p.name} v{p.version} - {p.description}")
    
    elif args.plugin_action == "load":
        if not args.name:
            print("Error: --name required")
            return 1
        success = pm.load_plugin(args.name)
        print(f"{'Loaded' if success else 'Failed to load'}: {args.name}")
    
    elif args.plugin_action == "unload":
        if not args.name:
            print("Error: --name required")
            return 1
        success = pm.unload_plugin(args.name)
        print(f"{'Unloaded' if success else 'Failed to unload'}: {args.name}")
    
    elif args.plugin_action == "scan":
        print(f"\n=== Plugin Directory: {pm.plugin_dir} ===")
        if os.path.exists(pm.plugin_dir):
            files = [f for f in os.listdir(pm.plugin_dir) if f.endswith(".py")]
            print(f"Available: {files}")
            print(f"Loaded:    {list(pm.plugins.keys())}")
        else:
            print("  (directory does not exist)")
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="ArduinoBridge CLI - Program Arduinos via REST API or CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # scan command
    p_scan = subparsers.add_parser("scan", help="Scan for available ports")
    p_scan.add_argument("--arduino-only", action="store_true", help="Show only Arduino-detected ports")
    p_scan.set_defaults(func=cmd_scan)
    
    # identify command
    p_id = subparsers.add_parser("identify", help="Identify board on a port")
    p_id.add_argument("--port", "-p", required=True, help="COM port or device path")
    p_id.set_defaults(func=cmd_identify)
    
    # flash command
    p_flash = subparsers.add_parser("flash", help="Flash firmware to a board")
    p_flash.add_argument("--port", "-p", required=True, help="COM port or device path")
    p_flash.add_argument("--board", "-b", required=True, help="Board type (uno, mega, nano, etc.)")
    p_flash.add_argument("--file", "-f", required=True, help="Firmware file (.hex or .bin)")
    p_flash.add_argument("--no-verify", action="store_true", help="Skip verification")
    p_flash.set_defaults(func=cmd_flash)
    
    # server command
    p_server = subparsers.add_parser("server", help="Start REST API server")
    p_server.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    p_server.add_argument("--port", "-p", type=int, default=8765, help="Port to bind to")
    p_server.add_argument("--debug", action="store_true", help="Enable debug mode")
    p_server.set_defaults(func=cmd_server)
    
    # plugins command
    p_plugins = subparsers.add_parser("plugins", help="Manage plugins")
    p_plugins.add_argument("plugin_action", choices=["list", "load", "unload", "scan"],
                          help="Action to perform")
    p_plugins.add_argument("--name", "-n", help="Plugin name")
    p_plugins.set_defaults(func=cmd_plugins)
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    if not args.command:
        parser.print_help()
        return 0
    
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())

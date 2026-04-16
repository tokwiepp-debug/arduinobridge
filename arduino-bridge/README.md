# ArduinoBridge

Cross-platform tool for programming Arduinos via OpenClaw / Melissa.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    OpenClaw / Melissa                   │
└─────────────────────────┬───────────────────────────────┘
                          │ HTTP/REST
┌─────────────────────────▼───────────────────────────────┐
│                    ArduinoBridge Core                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ Port Scanner│  │ Board ID    │  │ Flash Manager   │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
│  ┌─────────────────────────────────────────────────────┐│
│  │              Plugin System                          ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────┬───────────────────────────────┘
                          │ Serial/USB
                   ┌──────▼──────┐
                   │   Arduino   │
                   └─────────────┘
```

## Supported Platforms

- Windows (via PyInstaller as portable .exe)
- Linux
- Raspberry Pi (Linux ARM)
- Android (planned, via Termux or native app)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run CLI
python arduino_bridge.py scan

# Run server (for OpenClaw integration)
python arduino_bridge.py server
```

## API Endpoints (Server Mode)

- `GET /ports` - List available COM/USB ports
- `GET /board?port=COM3` - Identify board on port
- `POST /flash` - Flash firmware to board
- `GET /plugins` - List loaded plugins
- `POST /plugins/load` - Load a plugin

## Plugin System

Place `.py` plugins in the `plugins/` directory. Each plugin must implement:

```python
class Plugin:
    name: str
    version: str
    
    def on_port_detected(self, port_info: dict):
        """Called when a port is detected"""
        pass
    
    def on_board_identified(self, board_info: dict):
        """Called when a board is identified"""
        pass
    
    def on_flash_complete(self, result: dict):
        """Called after flashing completes"""
        pass
```

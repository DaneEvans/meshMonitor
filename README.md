# MeshViewer

A Meshtastic network monitoring application with both GUI and CLI interfaces.

## Features

- **GUI Interface**: Modern web-based interface using NiceGUI
- **CLI Interface**: Command-line monitoring for terminal-based workflows
- **Multiple Connection Types**: Support for both TCP and Serial connections
- **Real-time Monitoring**: Live updates of network node status
- **Battery Monitoring**: Track battery levels and charging status
- **Uptime Tracking**: Monitor node uptime and network health

## Plans 
Laptop hosted - unless I can port to an app as well? 
GUI, nicely formatted table / tabs, with health of all of your favourited nodes (ie. ones you admin)
Mostly it exists to ensure that your managed nodes are up, have decent battery levels, etc. 

## Todo:
- [ ] add GUI
- [ ] add history (db or whatever)
- [ ] add plots to show last week? of data
- [ ] add warnings / alerts
- [ ] look at bt / network interfaces
- [ ] look at running it on cloud, or sourcing data from mqtt. 

## Project Structure

```text
meshViewer/
├── src/
│   ├── __init__.py
│   ├── meshviewer/
│   │   ├── __init__.py
│   │   ├── connection.py      # Connection management
│   │   ├── interface.py       # Core Meshtastic interface
│   │   └── cli.py            # CLI interface
│   └── gui/
│       ├── __init__.py
│       └── main.py           # GUI interface
├── main.py                   # Main entry point (GUI)
├── setup.py                  # Package setup configuration
├── requirements.txt          # Dependencies
└── README.md
```

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd meshViewer
```

2. Install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## Usage

### GUI Mode (Default)

Run the web-based interface:

```bash
python main.py
```

The GUI will be available at `http://localhost:8080`

### CLI Mode

Run the command-line interface:

```bash
python -m src.meshviewer.cli --mode continuous --interval 30
```

#### CLI Options

- `--mode`: Display mode (`oneshot` or `continuous`)
- `--interval`: Refresh interval for continuous mode (seconds)
- `--tcp-host`: TCP host for connection (default: 192.168.0.114)
- `--tcp-port`: TCP port for connection (default: 4403)
- `--serial-port`: Serial port for connection (optional)

## Configuration

### TCP Connection

- Default host: `192.168.0.114`
- Default port: `4403`

### Serial Connection

- Auto-detect available ports
- Specify port manually if needed

## Development

The project is structured with clear separation of concerns:

- **`src/meshviewer/`**: Core Meshtastic functionality
  - `connection.py`: Handles network connections
  - `interface.py`: Node data processing and formatting
  - `cli.py`: Command-line interface

- **`src/gui/`**: GUI components
  - `main.py`: Web-based interface using NiceGUI

- **`main.py`**: Application entry point

## Dependencies

- `meshtastic`: Meshtastic Python library
- `nicegui`: Modern web UI framework
- `pyserial`: Serial communication
- `protobuf`: Protocol buffer support

## License

[Add your license information here]

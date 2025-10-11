# Mesh Monitor

MeshMonitor is a comprehensive Meshtastic network monitoring application designed to give you an 'at a glance' overview of your mesh network, with particular focus on nodes that you administer.

It is built using NiceGUI for the web interface and the [Meshtastic](https://meshtastic.org/) [python](https://github.com/meshtastic/python) library for network communication.

## Features

### Web Interface (GUI)
- **Local Web Server**: Served locally to enable viewing from any device on your network
- **Node Management**: Selectable 'favourites' or entire mesh view
- **Real-time Monitoring**: Battery levels, uptime, and last heard times for all nodes
- **Battery Alerts**: Audio and visual alerts at configurable battery thresholds
- **Battery History**: Interactive charts showing voltage trends over time (1 hour to 30 days)
- **Auto-connect**: Automatic connection to default network device
- **Auto-refresh**: Continuous data updates every 5 minutes
- **Responsive Design**: Works on mobile, tablet, and desktop
- **Data Persistence**: Automatic storage of node metrics to CSV/JSON files

### Command Line Interface (CLI)
- **One-shot Mode**: Single status report and exit
- **Continuous Mode**: Real-time monitoring with configurable refresh intervals
- **Multiple Connection Types**: TCP and Serial connections with automatic fallback
- **Terminal-friendly Output**: Formatted display optimized for terminal viewing

### Data Management
- **Automatic Logging**: Node data saved to `data/` directory
- **Historical Analysis**: Battery voltage trends and statistical summaries
- **Data Export**: CSV format for external analysis

MeshViewer can be run from a Raspberry Pi Zero, desktop computer, or any system with Python support. It communicates with nodes via either serial or TCP connections and is designed for continuous operation to provide comprehensive logging and analysis of mesh network health.


## Running 

The app is designed to be run on a RPi Zero, desktop computer, or any system with Python support.

### Quick Start
1. Clone this repository
2. Follow the installation instructions in [README.md](README.md)
3. Run the GUI: `python main.py`
4. Open your browser to `http://localhost:8080`

### GUI Mode (Default)
```bash
# Basic usage
python main.py

# With custom config
python main.py --config path/to/your_config.yaml

# Custom host/port
python main.py --host 127.0.0.1 --port 8081 --no-browser
```

### CLI Mode
```bash
# One-shot status report
python -m src.meshviewer.cli --mode oneshot

# Continuous monitoring
python -m src.meshviewer.cli --mode continuous --interval 30

# With custom connection settings
python -m src.meshviewer.cli --tcp-host 192.168.1.100 --tcp-port 4403
```

### Default Connection Settings
- **TCP Host**: `192.168.0.135` (configurable)
- **TCP Port**: `4403`
- **Web Interface**: `http://localhost:8080`

**Security Note**: This application is designed for hobbyist use on trusted networks. It is not intended for production or public-facing deployments.



## Configuring

Much of the application is configurable through the `config.yaml` file, including:

- **Theme Settings**: Colors, dark/light mode preferences
- **UI Text**: Customizable labels and messages
- **Connection Settings**: Default TCP host/port
- **Node Settings**: Active threshold hours for node activity detection
- **Battery Thresholds**: Alert levels for low battery warnings

The default configuration is located in `config.yaml` in the root directory. You can modify this file directly or provide an alternative configuration using the `--config` parameter.

### Configuration Options
- **App Settings**: Title, subtitle, logo path
- **Theme Colors**: Primary, secondary, accent, positive, negative colors
- **UI Text**: All user-facing text labels and messages
- **Connection Defaults**: TCP host (`192.168.0.135`) and port (`4403`)
- **Node Activity**: Threshold for considering nodes "active" (default: 3 hours)

## CLI Interface

The command-line interface provides comprehensive monitoring capabilities with both one-shot and continuous modes. Unlike the GUI, the CLI does not include data persistence directly, but output can be piped to log files for external processing.

[CLI API Documentation](./cli.md)

## Data Storage

MeshViewer automatically stores node data in the `data/` directory:
- **CSV Format**: `data/node_data.csv` - Structured data for analysis
- **JSON Format**: `data/node_data.json` - Complete node snapshots with timestamps

Data is saved every 5 minutes during normal operation, with intelligent filtering to only store nodes that have changed their uptime (indicating active status).

### Backup and restoring data

You can manually back up or restore the data storage files, or transfer them between machines as needed. This allows for long-term network logging. Please note that you are responsible for your own data management and backups.

Currently, there are no built-in limits on log file size. If you are monitoring a large network or have limited storage capacity, it is recommended to set up a cron job or similar process to periodically clean up or archive the log files.


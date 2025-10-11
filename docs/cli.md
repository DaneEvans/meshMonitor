# CLI API Documentation

The Mesh Monitor provides a command-line interface for monitoring and displaying network status information. The CLI is built around the `cli.py` module and offers both one-shot and continuous monitoring modes.

## Overview

The CLI allows you to:
- Monitor Meshtastic network nodes in real-time
- Display battery status, uptime, and connectivity information
- Connect via TCP or Serial interfaces
- Run in continuous monitoring mode with configurable refresh intervals
- Get one-shot status reports

## Usage

### Basic Command Structure

```bash
python -m src.meshviewer.cli [OPTIONS]
```

### Command Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--mode` | choice | `continuous` | Display mode: `oneshot` or `continuous` |
| `--interval` | int | `30` | Refresh interval for continuous mode (seconds) |
| `--tcp-host` | str | `192.168.0.114` | TCP host for connection |
| `--tcp-port` | int | `4403` | TCP port for connection |
| `--serial-port` | str | None | Serial port for connection (optional) |

## Modes

### One-shot Mode (`--mode oneshot`)

Displays a single snapshot of the network status and exits.

```bash
python -m src.meshviewer.cli --mode oneshot
```

**Output includes:**
- Network status header
- All nodes with device metrics showing:
  - Node ID
  - Long name (25 chars)
  - Hardware model (21 chars)
  - Battery status (level, voltage, charging status)
  - Last heard timestamp
  - Uptime in hours

### Continuous Mode (`--mode continuous`)

Continuously monitors the network with periodic updates.

```bash
python -m src.meshviewer.cli --mode continuous --interval 60
```

**Features:**
- Real-time monitoring with configurable refresh intervals
- Automatic data refresh before each display
- Last heard timestamp change detection
- Timestamped output with current time
- Graceful shutdown with Ctrl+C

## Connection Methods

### TCP Connection (Default)

The CLI attempts TCP connection by default:

```bash
python -m src.meshviewer.cli --tcp-host 192.168.1.100 --tcp-port 4403
```

### Serial Connection

For direct serial connection to a Meshtastic device:

```bash
python -m src.meshviewer.cli --serial-port /dev/ttyUSB0
```

### Fallback Behavior

When a serial port is specified but connection fails, the CLI automatically falls back to TCP connection.

## Output Format

### Node Information Display

Each node is displayed in the following format:

```
[node_id]  [long_name:25] - [hw_model:21] : [battery_info] : [last_heard] - [uptime]
```

**Example:**
```
!12345678  John's Node              - Heltec V3              :  85%, 3.7V  : last heard T-00:05:23 Ago - up 12.5 hrs
!87654321  Remote Station           - T-Beam V1.1            : Chg, 4.1V   : last heard T-00:01:45 Ago - up 8.2 hrs
```

### Battery Status Format

- **Normal battery**: `[level]%, [voltage]V` (e.g., `85%, 3.7V`)
- **Charging**: `Chg, [voltage]V` (e.g., `Chg, 4.1V`)

### Time Formats

- **Last heard**: `T-[HH:MM:SS] Ago` format showing time since last communication
- **Uptime**: `up [X.X] hrs` showing device uptime in hours

## Examples

### Quick Status Check
```bash
python -m src.meshviewer.cli --mode oneshot
```

### Continuous Monitoring with Custom Interval
```bash
python -m src.meshviewer.cli --mode continuous --interval 60
```

### Connect to Different TCP Host
```bash
python -m src.meshviewer.cli --tcp-host 10.0.0.100 --tcp-port 4403
```

### Serial Connection with Fallback
```bash
python -m src.meshviewer.cli --serial-port /dev/ttyUSB0 --tcp-host 192.168.1.50
```

## Error Handling

The CLI includes robust error handling:

- **Connection failures**: Clear error messages and automatic fallback
- **Keyboard interrupt**: Graceful shutdown with Ctrl+C
- **Data refresh errors**: Continues operation with warning messages
- **Invalid arguments**: Helpful usage information

## Integration

The CLI is designed to work seamlessly with the broader meshViewer ecosystem:

- Uses the same `MeshConnectionManager` as the GUI
- Leverages `MeshInterface` for consistent data handling
- Supports the same connection methods and protocols
- Compatible with data persistence features

## Troubleshooting

### Common Issues

1. **Connection refused**: Check TCP host/port or serial port permissions
2. **No data displayed**: Ensure the Meshtastic device is connected and active
3. **Permission denied**: For serial connections, ensure user has access to the device

### Debug Mode

For troubleshooting, you can enable debug output by modifying the CLI code to include the `debug=True` parameter in the `text_oneshot()` function call.

## Dependencies

The CLI requires:
- `argparse` for command-line argument parsing
- `time` for timing and formatting
- `MeshConnectionManager` from the connection module
- `MeshInterface` from the interface module

All dependencies are included in the standard meshMonitor installation.

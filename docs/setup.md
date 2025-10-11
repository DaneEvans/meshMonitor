
# Installation & Setup

This guide covers the complete installation and setup process for MeshMonitor.

## System Requirements

- **Python**: 3.8 or higher
- **Operating System**: Windows, macOS, or Linux
- **Memory**: 512MB RAM minimum (1GB recommended)
- **Storage**: 100MB for application and dependencies
- **Network**: Access to Meshtastic device via TCP or Serial connection

## Installation Methods

### Method 1: From Source (Recommended)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/daneevans/meshViewer.git
   cd meshViewer
   ```

2. **Create a virtual environment:**
   ```bash
   # Linux/macOS
   python3 -m venv .venv
   source .venv/bin/activate
   
   # Windows
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### Method 2: Using pip (Future)

```bash
pip install meshmonitor
```

## First Run

1. **Start the application:**
   ```bash
   python main.py
   ```

2. **Access the web interface:**
   - Open your browser to `http://localhost:8080`
   - The application will attempt to auto-connect to your Meshtastic device

3. **Configure connection (if needed):**
   - Use the connection panel in the web interface
   - Or modify `config.yaml` for default settings

## Connection Setup

### TCP Connection (Default)
- **Default Host**: `192.168.0.135`
- **Default Port**: `4403`
- **Use Case**: When your Meshtastic device is connected to WiFi

### Serial Connection
- **Auto-detection**: Available serial ports are automatically detected
- **Manual specification**: Use `--serial-port` parameter
- **Use Case**: Direct USB connection to Meshtastic device

## Troubleshooting

### Common Issues

#### Port Already in Use
```bash
# Kill process using port 8080
lsof -ti:8080 | xargs kill -9  # Linux/macOS
netstat -ano | findstr :8080   # Windows
```

#### Connection Failed
1. **Check device connectivity:**
   - Ensure Meshtastic device is powered on
   - Verify network connection (for TCP)
   - Check USB connection (for Serial)

2. **Verify settings:**
   - Confirm correct IP address and port
   - Check serial port permissions (Linux/macOS)

3. **Test with CLI:**
   ```bash
   python -m src.meshviewer.cli --mode oneshot
   ```

#### Permission Denied (Serial)
```bash
# Add user to dialout group (Linux)
sudo usermod -a -G dialout $USER
# Log out and back in
```

### Performance Issues

#### Large Network
- Increase refresh interval in continuous mode
- Consider using CLI mode for better performance
- Monitor disk space for data logs

#### Memory Usage
- Close other applications if running on limited hardware
- Use oneshot mode instead of continuous monitoring

## Data Directory

MeshMonitor creates a `data/` directory for storing:
- `node_data.csv` - Structured node metrics
- `node_data.json` - Complete node snapshots

**Note**: Ensure the application has write permissions to the installation directory.

## Uninstallation

1. **Stop the application** (Ctrl+C)
2. **Remove the directory:**
   ```bash
   rm -rf meshViewer/  # Linux/macOS
   rmdir /s meshViewer  # Windows
   ```

## Next Steps

- [Configuration Guide](configuration.md) - Customize themes, settings, and behavior
- [CLI Reference](cli.md) - Command-line interface documentation
- [Main Documentation](index.md) - Complete feature overview


### Autorun on the pi. 

https://www.dexterindustries.com/howto/run-a-program-on-your-raspberry-pi-at-startup/

using /home/dane/.bashrc
# Configuration Guide

MeshMonitor is highly configurable through the `config.yaml` file. This guide covers all available configuration options and their usage.

## Configuration File Location

- **Default**: `config.yaml` in the application root directory
- **Custom**: Specify with `--config path/to/your_config.yaml`

## Configuration Sections

### Application Settings

```yaml
app:
  title: "MeshMonitor"
  subtitle: "Meshtastic Network Monitor"
  page_title: "MeshMonitor - Meshtastic Network Monitor"
  logo_path: "assets/M-PWRD.png"
  contactname: "Site by Dane Evans"
  contactsite: "https://daneevans.github.io/meshMonitor/"
```

**Options:**
- `title`: Main application title displayed in the UI
- `subtitle`: Subtitle text below the main title
- `page_title`: Browser tab title
- `logo_path`: Path to logo image file (relative to application root)
- `contactname`: Contact attribution text displayed in the UI
- `contactsite`: URL for the contact attribution link

### Theme Configuration

```yaml
theme:
  colors:
    primary: "#2c2d3c"      # Main background color
    secondary: "#234d20"    # Secondary background color
    accent: "#c9df8a"       # Accent color for highlights
    positive: "#21BA45"     # Success/positive indicators
    negative: "#C10015"     # Error/negative indicators
  # dark_mode: true         # Uncomment to enable dark mode by default
```

**Color Usage:**
- `primary`: Main UI background and primary elements
- `secondary`: Secondary panels and cards
- `accent`: Highlights, borders, and interactive elements
- `positive`: Battery levels > 60%, successful connections
- `negative`: Battery levels < 60%, connection failures

### UI Text Customization

```yaml
ui_text:
  connection:
    title: "Connection"
    disconnected_status: "Disconnected"
    connected_tcp_status: "Connected via TCP to {host}:{port}"
    connected_serial_status: "Connected via Serial on {port}"
    connection_failed_tcp: "TCP connection failed"
    connection_failed_serial: "Serial connection failed"
  
  nodes:
    title_favorites: "Favourite Nodes"
    title_all: "All Mesh Nodes"
    no_nodes_found: "No nodes found"
    not_connected: "Not connected"
    channel_util_label: "Channel Util"
    hw_label: "HW"
    user_id_label: "User ID"
```

**Customization:**
- All user-facing text can be customized
- Use `{variable}` syntax for dynamic content (e.g., `{host}`, `{port}`)
- Supports multiple languages by creating different config files

### Connection Settings

```yaml
connection:
  default_tcp_host: "192.168.0.135"
  default_tcp_port: 4403
```

**Options:**
- `default_tcp_host`: Default IP address for TCP connections
- `default_tcp_port`: Default port for TCP connections

### Node Activity Settings

```yaml
nodes:
  active_threshold_hours: 3
```

**Options:**
- `active_threshold_hours`: Hours since last communication to consider a node "active"

## Configuration Examples

### Dark Mode Configuration

```yaml
theme:
  colors:
    primary: "#1a1a1a"
    secondary: "#2d2d2d"
    accent: "#4a9eff"
    positive: "#4caf50"
    negative: "#f44336"
  dark_mode: true
```

### Custom Branding

```yaml
app:
  title: "My Mesh Network"
  subtitle: "Custom Network Monitor"
  page_title: "My Mesh - Network Status"
  logo_path: "assets/my-logo.png"

ui_text:
  connection:
    title: "Network Connection"
    connected_tcp_status: "Connected to {host}:{port}"
```

### High-Contrast Theme

```yaml
theme:
  colors:
    primary: "#000000"
    secondary: "#ffffff"
    accent: "#ffff00"
    positive: "#00ff00"
    negative: "#ff0000"
```

## Runtime Configuration

### Command Line Options

```bash
# Use custom config file
python main.py --config /path/to/custom_config.yaml

# Override host and port
python main.py --host 0.0.0.0 --port 8081

# Disable browser auto-open
python main.py --no-browser
```

### CLI Configuration

```bash
# Custom TCP connection
python -m src.meshviewer.cli --tcp-host 192.168.1.100 --tcp-port 4403

# Serial connection
python -m src.meshviewer.cli --serial-port /dev/ttyUSB0

# Custom refresh interval
python -m src.meshviewer.cli --mode continuous --interval 60
```

## Advanced Configuration

### Environment Variables

You can override configuration values using environment variables:

```bash
export MESHMONITOR_TCP_HOST="192.168.1.50"
export MESHMONITOR_TCP_PORT="4403"
python main.py
```

### Multiple Configurations

Create different configuration files for different environments:

```bash
# Development
python main.py --config config_dev.yaml

# Production
python main.py --config config_prod.yaml

# Testing
python main.py --config config_test.yaml
```

### Configuration Validation

The application validates configuration files on startup. Common validation errors:

- **Invalid color format**: Use hex colors (e.g., `#ff0000`)
- **Missing required fields**: Ensure all required sections are present
- **Invalid file paths**: Check that logo and asset paths are correct
- **Invalid port numbers**: Use valid port numbers (1-65535)

## Best Practices

### Performance
- Use appropriate refresh intervals for your network size
- Consider using CLI mode for large networks
- Monitor disk space for data logs

### Security
- Use trusted networks only
- Consider firewall rules for production deployments
- Regularly update dependencies

### Maintenance
- Backup configuration files
- Document custom configurations
- Test configuration changes in development first

## Troubleshooting Configuration

### Common Issues

#### Configuration Not Loading
1. Check file path and permissions
2. Validate YAML syntax
3. Ensure all required sections are present

#### Theme Not Applying
1. Verify color format (hex codes)
2. Check for typos in color names
3. Restart application after changes

#### Connection Settings Not Working
1. Verify IP address and port
2. Check network connectivity
3. Test with CLI mode first

### Configuration Reset

To reset to defaults:
1. Delete or rename current `config.yaml`
2. Restart the application
3. A new default configuration will be created

## Next Steps

- [Installation Guide](setup.md) - Complete setup instructions
- [CLI Reference](cli.md) - Command-line interface documentation
- [Main Documentation](index.md) - Feature overview and usage


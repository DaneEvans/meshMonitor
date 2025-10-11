# MeshMonitor

[MeshMonitor](https://daneevans.github.io/meshMonitor/) is a comprehensive Meshtastic network monitoring application with both GUI and CLI interfaces for monitoring your mesh network nodes.


## Screenshots

MeshMonitor using in default configuration

**Front Page**
![MeshMonitor Desktop Front Page](desktop_frontpage_default.png)

**Graph View**
![MeshMonitor Desktop Graph View](desktop_graph_default.png)

## Quick Start

1. **Clone and install:**
   ```bash
   git clone https://github.com/daneevans/meshViewer.git
   cd meshViewer
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Run the application:**
   ```bash
   python main.py

   # run from ssh - no hangup 
   nohup python main.py &
   ```

3. **Open your browser to:** `http://localhost:8080`

## Features

- 🌐 **Web Interface**: Modern responsive UI with real-time monitoring
- 📊 **Battery History**: Interactive charts showing voltage trends over time
- 🔔 **Smart Alerts**: Audio and visual notifications for low battery
- 💾 **Data Persistence**: Automatic CSV/JSON logging with intelligent filtering
- 🖥️ **CLI Interface**: Terminal-based monitoring for automation
- 🔌 **Multiple Connections**: TCP and Serial support with auto-fallback
- 🎨 **Customizable**: Themes, colors, and UI text via config.yaml

## Documentation

📖 **[Full Documentation](https://daneevans.github.io/meshMonitor/)** - Complete user guide, configuration, and API reference

- [Installation & Setup](https://daneevans.github.io/meshMonitor/setup)
- [CLI Reference](https://daneevans.github.io/meshMonitor/cli)
- [Configuration Guide](https://daneevans.github.io/meshMonitor/configuration)

## Requirements

- Python 3.8+
- Meshtastic device via serial or network access
- Modern web browser (for GUI)

## License

[Add your license information here]

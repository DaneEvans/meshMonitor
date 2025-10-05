#!/usr/bin/env python3
"""
MeshViewer - A Meshtastic network monitoring application.

This is the main entry point for the application.
"""
import sys
import signal
import atexit
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from gui.main import MeshViewerGUI


class MeshViewerApp:
    """Main application class with proper signal handling."""
    
    def __init__(self):
        self.app = None
        self.server = None
        
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, _frame):
            print(f"\nReceived signal {signum}. Shutting down gracefully...")
            self.cleanup()
            sys.exit(0)
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # kill command
        
        # Register cleanup function to run on exit
        atexit.register(self.cleanup)
    
    def cleanup(self):
        """Clean up resources and close connections."""
        if self.app and hasattr(self.app, 'connection_manager'):
            print("Disconnecting from mesh network...")
            self.app.connection_manager.disconnect()
        
        if self.server:
            print("Stopping web server...")
            try:
                self.server.stop()
            except (AttributeError, RuntimeError) as e:
                print(f"Error stopping server: {e}")
        
        print("Cleanup completed.")
    
    def run(self, host='0.0.0.0', port=8080, show=True):
        """Run the application with proper signal handling."""
        print("Starting MeshViewer...")
        print("Use Ctrl+C to terminate.")
        
        # Setup signal handlers
        self.setup_signal_handlers()
        
        # Create and run the GUI
        self.app = MeshViewerGUI()
        self.app.setup_ui()
        
        try:
            # Start the server
            from nicegui import ui
            self.server = ui.run(host=host, port=port, show=show)
        except KeyboardInterrupt:
            print("\nReceived keyboard interrupt. Shutting down...")
        except (ImportError, RuntimeError) as e:
            print(f"Error running application: {e}")
        finally:
            self.cleanup()


def main():
    """Main entry point for the application."""
    app = MeshViewerApp()
    app.run(host='0.0.0.0', port=8080, show=True)


if __name__ in {"__main__", "__mp_main__"}:
    main()

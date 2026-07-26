#!/usr/bin/env python3
"""MeshViewer application entry point packaged with the source tree."""

import atexit
import signal
import sys
import threading
import traceback
import os
from pathlib import Path
from datetime import datetime


src_path = Path(__file__).resolve().parents[1]
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from gui.main import MeshViewerGUI


class _TeeStream:
    """Write to both console and a log file."""

    def __init__(self, console_stream, log_stream):
        self.console_stream = console_stream
        self.log_stream = log_stream

    def write(self, data):
        if not data:
            return 0
        try:
            self.console_stream.write(data)
        except Exception:
            pass
        try:
            self.log_stream.write(data)
        except Exception:
            pass
        return len(data)

    def flush(self):
        try:
            self.console_stream.flush()
        except Exception:
            pass
        try:
            self.log_stream.flush()
        except Exception:
            pass

    def isatty(self):
        try:
            return bool(self.console_stream.isatty())
        except Exception:
            return False


_LOG_SETUP_DONE = False
_LOG_FILE_HANDLE = None


def _setup_runtime_logging() -> Path:
    """Route stdout/stderr and uncaught exceptions to runlogs/meshmonitor.log."""
    global _LOG_SETUP_DONE, _LOG_FILE_HANDLE

    project_root = Path(__file__).resolve().parents[2]
    log_dir = project_root / 'runlogs'
    log_dir.mkdir(parents=True, exist_ok=True)

    log_path = Path((
        os.environ.get('MESHMONITOR_LOG_FILE')
        or str(log_dir / 'meshmonitor.log')
    )).expanduser()
    if not log_path.is_absolute():
        log_path = (project_root / log_path).resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if _LOG_SETUP_DONE:
        return log_path

    _LOG_FILE_HANDLE = open(log_path, 'a', encoding='utf-8', buffering=1)
    _LOG_FILE_HANDLE.write(
        f"\n===== MeshMonitor start {datetime.now().isoformat(timespec='seconds')} =====\n"
    )

    sys.stdout = _TeeStream(sys.__stdout__, _LOG_FILE_HANDLE)
    sys.stderr = _TeeStream(sys.__stderr__, _LOG_FILE_HANDLE)

    def _log_uncaught(exc_type, exc_value, exc_tb):
        traceback.print_exception(exc_type, exc_value, exc_tb, file=sys.stderr)

    def _log_thread_uncaught(args):
        traceback.print_exception(args.exc_type, args.exc_value, args.exc_traceback, file=sys.stderr)

    sys.excepthook = _log_uncaught
    if hasattr(threading, 'excepthook'):
        threading.excepthook = _log_thread_uncaught

    _LOG_SETUP_DONE = True
    print(f"Logging to {log_path}")
    return log_path


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

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
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

    def run(self, host='0.0.0.0', port=8080, show=True, config_path=None):
        """Run the application with proper signal handling."""
        print("Starting MeshViewer...")
        print("Use Ctrl+C to terminate.")

        self.setup_signal_handlers()
        self.app = MeshViewerGUI(config_path=config_path)
        self.app.setup_ui()

        try:
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
    _setup_runtime_logging()
    app = MeshViewerApp()
    import argparse

    parser = argparse.ArgumentParser(description='MeshViewer Application')
    parser.add_argument('--config', type=str, default=None, help='Path to configuration YAML file')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Server host address')
    parser.add_argument('--port', type=int, default=8080, help='Server port')
    parser.add_argument('--no-browser', dest='show', action='store_false', help="Don't open web browser automatically")
    parser.set_defaults(show=True)

    args = parser.parse_args()

    app.run(host=args.host, port=args.port, show=args.show, config_path=args.config)


if __name__ in {'__main__', '__mp_main__'}:
    main()
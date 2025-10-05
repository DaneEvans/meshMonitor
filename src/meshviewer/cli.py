"""
Command-line interface for Meshtastic network monitoring.
"""
import time
import argparse
from typing import Optional
from .connection import MeshConnectionManager
from .interface import MeshInterface


def text_oneshot(mesh_interface: MeshInterface, debug=False) -> None:
    """
    Text-based one-shot display of network status.
    
    Args:
        mesh_interface: MeshInterface instance
    """
    print("=== Meshtastic Network Status ===")
    mesh_interface.get_battery_string(whole_mesh=True)
    print()

    if debug:
        mesh_interface.get_single_node_dump()
        print()


def continuous_text(mesh_interface: MeshInterface, interval: int = 30) -> None:
    """
    Continuous text-based monitoring of network status.
    
    Args:
        mesh_interface: MeshInterface instance
        interval: Refresh interval in seconds
    """
    print("Starting continuous monitoring... (Press Ctrl+C to stop)")
    
    try:
        while True:
            curr_time = time.strftime("%H:%M:%S", time.localtime())
            print(f"\nCurrent Time: {curr_time}")
            print("=" * 50)
            mesh_interface.get_battery_string(whole_mesh=True)
            print()
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Meshtastic Network Monitor CLI")
    parser.add_argument("--mode", choices=["oneshot", "continuous"], default="continuous",
                       help="Display mode: oneshot or continuous")
    parser.add_argument("--interval", type=int, default=30,
                       help="Refresh interval for continuous mode (seconds)")
    parser.add_argument("--tcp-host", type=str, default="192.168.0.114",
                       help="TCP host for connection")
    parser.add_argument("--tcp-port", type=int, default=4403,
                       help="TCP port for connection")
    parser.add_argument("--serial-port", type=str,
                       help="Serial port for connection (optional)")
    
    args = parser.parse_args()
    
    # Setup connection
    connection_manager = MeshConnectionManager()
    
    # Try TCP connection first, then serial if specified
    if args.serial_port:
        if not connection_manager.connect_serial(args.serial_port):
            print("Serial connection failed, trying TCP...")
            if not connection_manager.connect_tcp(args.tcp_host, args.tcp_port):
                print("All connection attempts failed!")
                return
    else:
        if not connection_manager.connect_tcp(args.tcp_host, args.tcp_port):
            print("TCP connection failed!")
            return
    
    # Create mesh interface
    mesh_interface = MeshInterface(connection_manager.get_interface())
    
    # Run based on mode
    if args.mode == "oneshot":
        text_oneshot(mesh_interface)
    else:
        continuous_text(mesh_interface, args.interval)
    
    # Cleanup
    connection_manager.disconnect()


if __name__ == "__main__":
    main()

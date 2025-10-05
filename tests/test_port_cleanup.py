#!/usr/bin/env python3
"""
Test script to verify port cleanup works properly.
This script checks if port 8080 is available before and after running main.py
"""
import subprocess
import time
import socket
import sys
import signal
import os
from pathlib import Path


def is_port_in_use(port):
    """Check if a port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('localhost', port))
            return False
        except OSError:
            return True


def test_port_cleanup():
    """Test that the port is properly released when the process is killed."""
    port = 8080
    
    print(f"Testing port {port} cleanup...")
    
    # Check if port is initially available
    if is_port_in_use(port):
        print(f"❌ Port {port} is already in use. Please free it first.")
        return False
    
    print(f"✅ Port {port} is initially available")
    
    # Start the application
    print("Starting main.py...")
    main_py_path = Path(__file__).parent.parent / 'main.py'
    process = subprocess.Popen([sys.executable, str(main_py_path)], 
                             stdout=subprocess.PIPE, 
                             stderr=subprocess.PIPE)
    
    # Wait a moment for the server to start
    time.sleep(3)
    
    # Check if port is now in use
    if is_port_in_use(port):
        print(f"✅ Port {port} is now in use (server started)")
    else:
        print(f"❌ Port {port} is not in use (server failed to start)")
        process.terminate()
        return False
    
    # Kill the process
    print("Killing the process...")
    process.terminate()
    
    # Wait for cleanup
    time.sleep(2)
    
    # Check if port is released
    if not is_port_in_use(port):
        print(f"✅ Port {port} has been properly released")
        return True
    else:
        print(f"❌ Port {port} is still in use (cleanup failed)")
        return False


if __name__ == "__main__":
    success = test_port_cleanup()
    sys.exit(0 if success else 1)

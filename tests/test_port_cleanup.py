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
from datetime import datetime


def is_port_in_use(port):
    """Check if a port is in use.

    On Windows, a pure "bind test" can produce false negatives depending on how the
    server socket is created (reuse/exclusive flags). Prefer an active connect test.
    """
    # 1) Active connect test (most reliable for our use-case)
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.25):
            return True
    except (ConnectionRefusedError, TimeoutError, OSError):
        pass

    # 2) Fallback: try exclusive bind (better than a normal bind on Windows)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # Windows-only: request exclusive use so bind accurately detects conflicts.
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                try:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                except OSError:
                    pass
            s.bind(("127.0.0.1", port))
            return False
    except OSError:
        return True


def test_port_cleanup():
    """Test that the port is properly released when the process is killed."""
    port = 8080
    startup_timeout_s = 25
    
    print(f"Testing port {port} cleanup...")
    
    # Check if port is initially available
    if is_port_in_use(port):
        print(f"[FAIL] Port {port} is already in use. Please free it first.")
        return False
    
    print(f"[OK] Port {port} is initially available")
    
    # Start the application
    print("Starting main.py...")
    main_py_path = Path(__file__).parent.parent / 'main.py'
    project_root = Path(__file__).parent.parent
    logs_dir = project_root / "runlogs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = logs_dir / f"test_port_cleanup_main_{timestamp}.log"

    log_file = open(log_path, "w", encoding="utf-8", errors="replace")
    log_file.write(f"sys.executable: {sys.executable}\n")
    log_file.write(f"cwd: {project_root}\n")
    log_file.write(f"command: {sys.executable} {main_py_path}\n")
    log_file.write("=" * 80 + "\n")
    log_file.flush()

    # On Windows, run in a new process group so we can send CTRL_BREAK for a clean shutdown.
    creationflags = 0
    if os.name == "nt" and hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    process = subprocess.Popen(
        [sys.executable, str(main_py_path)],
        cwd=str(project_root),
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=creationflags or 0,
    )
    
    # Wait for the server to start (or fail), up to a timeout.
    started = False
    start_time = time.time()
    while time.time() - start_time < startup_timeout_s:
        if process.poll() is not None:
            # Process exited early; port will not come up.
            break
        if is_port_in_use(port):
            started = True
            break
        time.sleep(0.25)
    
    # Check if port is now in use
    if started or is_port_in_use(port):
        print(f"[OK] Port {port} is now in use (server started)")
    else:
        exit_code = process.poll()
        print(f"[FAIL] Port {port} is not in use (server failed to start)")
        if exit_code is not None:
            print(f"[FAIL] main.py exited early with code {exit_code}; see log: {log_path}")
        else:
            print(f"[FAIL] main.py did not bind within {startup_timeout_s}s; see log: {log_path}")
        try:
            process.terminate()
        finally:
            try:
                log_file.flush()
                log_file.close()
            except Exception:
                pass
        return False
    
    # Kill the process (try graceful signal first so cleanup runs)
    print("Killing the process...")
    try:
        if os.name == "nt":
            # Send CTRL_BREAK_EVENT to the new process group so Python's signal
            # handlers (SIGINT/SIGTERM) in main.py can run cleanup().
            try:
                process.send_signal(signal.CTRL_BREAK_EVENT)
            except (ValueError, OSError, AttributeError):
                process.terminate()
        else:
            process.send_signal(signal.SIGINT)
    except Exception:
        # Fallback to terminate if signals fail
        try:
            process.terminate()
        except Exception:
            pass

    try:
        process.wait(timeout=10)
    except Exception:
        # Last resort: force kill
        try:
            process.kill()
        except Exception:
            pass
    
    # Wait for cleanup
    time.sleep(10)
    
    # Check if port is released
    if not is_port_in_use(port):
        print(f"[OK] Port {port} has been properly released")
        try:
            log_file.flush()
            log_file.close()
        except Exception:
            pass
        return True
    else:
        print(f"[FAIL] Port {port} is still in use (cleanup failed)")
        try:
            log_file.flush()
            log_file.close()
        except Exception:
            pass
        return False


if __name__ == "__main__":
    success = test_port_cleanup()
    sys.exit(0 if success else 1)

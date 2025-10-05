#!/usr/bin/env python3
"""
Test script to verify the refactored structure works correctly.
"""
import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

def test_imports():
    """Test that all modules can be imported correctly."""
    try:
        from meshtastic.connection import MeshConnectionManager
        from meshtastic.interface import MeshInterface
        from meshtastic.cli import main as cli_main
        from gui.main import MeshViewerGUI
        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def test_connection_manager():
    """Test connection manager initialization."""
    try:
        from meshtastic.connection import MeshConnectionManager
        manager = MeshConnectionManager()
        assert not manager.is_connected()
        print("✓ Connection manager works")
        return True
    except Exception as e:
        print(f"✗ Connection manager error: {e}")
        return False

def test_gui_initialization():
    """Test GUI initialization."""
    try:
        from gui.main import MeshViewerGUI
        gui = MeshViewerGUI()
        assert gui.connection_manager is not None
        assert not gui.connected
        print("✓ GUI initialization works")
        return True
    except Exception as e:
        print(f"✗ GUI initialization error: {e}")
        return False

def main():
    """Run all tests."""
    print("Testing refactored MeshViewer structure...")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_connection_manager,
        test_gui_initialization
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"Tests passed: {passed}/{len(tests)}")
    
    if passed == len(tests):
        print("✓ All tests passed! Structure is working correctly.")
    else:
        print("✗ Some tests failed. Check the errors above.")

if __name__ == "__main__":
    main()

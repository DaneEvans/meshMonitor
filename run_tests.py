#!/usr/bin/env python3
"""
Test runner for MeshViewer application.
Runs all available tests in the tests directory.
"""
import sys
import subprocess
from pathlib import Path


def run_test(test_file):
    """Run a single test file and return success status."""
    print(f"\n{'='*60}")
    print(f"Running {test_file.name}...")
    print('='*60)
    
    try:
        result = subprocess.run([sys.executable, str(test_file)], 
                              capture_output=False, 
                              text=True)
        return result.returncode == 0
    except Exception as e:
        print(f"Error running {test_file.name}: {e}")
        return False


def main():
    """Run all tests."""
    print("MeshViewer Test Suite")
    print("="*60)
    
    tests_dir = Path(__file__).parent / "tests"
    
    if not tests_dir.exists():
        print("❌ Tests directory not found!")
        return False
    
    # Find all test files
    test_files = list(tests_dir.glob("test_*.py"))
    
    if not test_files:
        print("❌ No test files found in tests directory!")
        return False
    
    print(f"Found {len(test_files)} test file(s)")
    
    # Run all tests
    passed = 0
    total = len(test_files)
    
    for test_file in test_files:
        if run_test(test_file):
            passed += 1
            print(f"✅ {test_file.name} PASSED")
        else:
            print(f"❌ {test_file.name} FAILED")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Test Results: {passed}/{total} tests passed")
    print('='*60)
    
    if passed == total:
        print("🎉 All tests passed!")
        return True
    else:
        print("💥 Some tests failed!")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

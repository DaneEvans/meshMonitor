#!/bin/bash
# Installation script for MeshViewer

echo "Installing MeshViewer..."

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    exit 1
fi

# Check if pip is available
if ! command -v pip3 &> /dev/null; then
    echo "Error: pip3 is required but not installed."
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
pip3 install -r requirements.txt

# Make scripts executable
chmod +x main.py
chmod +x run_tests.py
chmod +x tests/test_structure.py
chmod +x tests/test_port_cleanup.py

echo "Installation complete!"
echo ""
echo "To run the GUI version:"
echo "  python3 main.py"
echo ""
echo "To run the CLI version:"
echo "  python3 -m src.meshtastic.cli --help"
echo ""
echo "To run all tests:"
echo "  python3 run_tests.py"
echo ""
echo "To test the installation:"
echo "  python3 tests/test_structure.py"
echo ""
echo "To test port cleanup:"
echo "  python3 tests/test_port_cleanup.py"

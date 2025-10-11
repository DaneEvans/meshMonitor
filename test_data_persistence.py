#!/usr/bin/env python3
"""
Test script for data persistence functionality.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from meshviewer.data_persistence import DataPersistence
import time
from datetime import datetime

def test_data_persistence():
    """Test the data persistence functionality."""
    print("Testing DataPersistence...")
    
    # Initialize data persistence
    dp = DataPersistence("test_data")
    
    # Create some test data
    test_nodes = {
        "!12345678": {
            "user": {
                "shortName": "Test1",
                "longName": "Test Node 1",
                "hwModel": "T-Beam"
            },
            "deviceMetrics": {
                "batteryLevel": 85,
                "voltage": 3.7,
                "uptimeSeconds": 3600,
                "channelUtilization": 15.5
            },
            "lastHeard": int(time.time()),
            "isFavorite": True
        },
        "!87654321": {
            "user": {
                "shortName": "Test2", 
                "longName": "Test Node 2",
                "hwModel": "Heltec"
            },
            "deviceMetrics": {
                "batteryLevel": 45,
                "voltage": 3.2,
                "uptimeSeconds": 7200,
                "channelUtilization": 8.2
            },
            "lastHeard": int(time.time()) - 1800,
            "isFavorite": False
        }
    }
    
    # Save test data
    print("Saving test data...")
    dp.save_nodes_data(test_nodes)
    
    # Test getting battery history
    print("Getting battery history...")
    df = dp.get_battery_history(7)
    print(f"Retrieved {len(df)} records")
    if not df.empty:
        print("Sample data:")
        print(df.head())
    
    # Test getting data summary
    print("Getting data summary...")
    summary = dp.get_data_summary()
    print(f"Summary: {summary}")
    
    # Test getting specific node history
    print("Getting specific node history...")
    node_df = dp.get_node_battery_history("!12345678", 7)
    print(f"Node history: {len(node_df)} records")
    
    print("Data persistence test completed successfully!")

if __name__ == "__main__":
    test_data_persistence()

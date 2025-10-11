"""
Data persistence module for storing node data and battery history.
"""
import csv
import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import pandas as pd


class DataPersistence:
    """Handles data persistence for node metrics and battery history."""
    
    def __init__(self, data_dir: str = "data"):
        """
        Initialize the data persistence manager.
        
        Args:
            data_dir: Directory to store data files
        """
        self.data_dir = data_dir
        self.csv_file = os.path.join(data_dir, "node_data.csv")
        self.json_file = os.path.join(data_dir, "node_data.json")
        
        # Create data directory if it doesn't exist
        os.makedirs(data_dir, exist_ok=True)
        
        # Initialize CSV file with headers if it doesn't exist
        self._initialize_csv()
        
        # Track previous uptime values to detect changes
        self._previous_uptimes = {}
        
        # Load previous uptime values from existing data
        self._load_previous_uptimes()
    
    def _initialize_csv(self) -> None:
        """Initialize CSV file with headers if it doesn't exist."""
        if not os.path.exists(self.csv_file):
            headers = [
                'timestamp', 'node_id', 'short_name', 'long_name', 'hw_model',
                'battery_level', 'voltage', 'is_charging', 'uptime_hours',
                'channel_utilization', 'last_heard', 'is_favorite'
            ]
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
    
    def _load_previous_uptimes(self) -> None:
        """Load the most recent uptime values for each node from existing data."""
        if not os.path.exists(self.csv_file):
            return
        
        try:
            df = pd.read_csv(self.csv_file)
            if df.empty:
                return
            
            # Get the most recent uptime for each node
            latest_data = df.groupby('node_id')['uptime_hours'].last()
            self._previous_uptimes = latest_data.to_dict()
            
        except Exception as e:
            print(f"Warning: Could not load previous uptime values: {e}")
            self._previous_uptimes = {}
    
    def save_nodes_data(self, nodes_data: Dict[str, Dict[str, Any]]) -> None:
        """
        Save current nodes data to both CSV and JSON files.
        
        Args:
            nodes_data: Dictionary of node data keyed by node ID
        """
        timestamp = int(time.time())
        timestamp_str = datetime.fromtimestamp(timestamp).isoformat()
        
        # Check if we already have data for this timestamp to avoid duplicates
        if os.path.exists(self.csv_file):
            try:
                existing_df = pd.read_csv(self.csv_file)
                if not existing_df.empty:
                    # Check if we already have data for this exact timestamp
                    existing_df['timestamp'] = pd.to_datetime(existing_df['timestamp'])

                    # Find the latest timestamp and compare to current; skip if less than 4 minutes (240 seconds) after last one
                    if not existing_df['timestamp'].empty:
                        latest_existing_ts = existing_df['timestamp'].max()
                        current_ts = pd.to_datetime(timestamp_str)
                        time_diff = (current_ts - latest_existing_ts).total_seconds()
                        if time_diff < 240:
                            print(f"Data for timestamp {timestamp_str} is less than 4 minutes after previous ({latest_existing_ts}), skipping save")
                            return
            except Exception as e:
                print(f"Warning: Could not check for existing data: {e}")
        
        # Prepare data for CSV
        csv_rows = []
        json_data = {
            'timestamp': timestamp,
            'timestamp_str': timestamp_str,
            'nodes': {}
        }
        
        for node_id, node in nodes_data.items():
            # Skip nodes without device metrics
            if 'deviceMetrics' not in node:
                continue
                
            # Extract uptime and check if it has changed
            uptime_hours = node['deviceMetrics'].get('uptimeSeconds', 0) / 3600
            previous_uptime = self._previous_uptimes.get(node_id, 0)
            
            print(f"watchme: {uptime_hours}, {previous_uptime}")
            # Skip nodes that haven't changed their uptime (indicating they haven't updated telemetry.
            # Allow small float precision differences and optionally a force-write override in the future
            uptime_diff = abs(float(uptime_hours) - float(previous_uptime))
            # Consider uptime the "same" if the change is less than 0.01 hour (36 seconds)
            if uptime_diff < 0.01:
                print(f'skipping writing to db for node {node_id} (uptime difference {uptime_diff:.4f} < 0.0001)')
                continue
            else:
                print(f' writing to db for node {node_id} (uptime difference {uptime_diff:.4f} >= 0.0001)')            # Extract battery information
            battery_level = node['deviceMetrics'].get('batteryLevel', 0)
            voltage = node['deviceMetrics'].get('voltage', 0.0)
            is_charging = battery_level == 101
            
            # Extract other metrics
            channel_util = node['deviceMetrics'].get('channelUtilization', 0.0)
            last_heard = node.get('lastHeard', 0)
            
            # Extract user information
            user_info = node.get('user', {})
            short_name = user_info.get('shortName', 'Unknown')
            long_name = user_info.get('longName', 'Unknown')
            hw_model = user_info.get('hwModel', 'Unknown')
            
            # Check if favorite
            is_favorite = 'isFavorite' in node
            
            # CSV row
            csv_row = [
                timestamp_str, node_id, short_name, long_name, hw_model,
                battery_level, voltage, is_charging, uptime_hours,
                channel_util, last_heard, is_favorite
            ]
            csv_rows.append(csv_row)
            
            # JSON data
            json_data['nodes'][node_id] = {
                'user': {
                    'shortName': short_name,
                    'longName': long_name,
                    'hwModel': hw_model
                },
                'deviceMetrics': {
                    'batteryLevel': battery_level,
                    'voltage': voltage,
                    'isCharging': is_charging,
                    'uptimeHours': uptime_hours,
                    'channelUtilization': channel_util
                },
                'lastHeard': last_heard,
                'isFavorite': is_favorite
            }
        
        # Write to CSV
        with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(csv_rows)
        
        # Write to JSON (append to file with timestamp)
        with open(self.json_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(json_data) + '\n')
        
        # Update the previous uptime tracking for saved nodes
        for node_id, node in nodes_data.items():
            if 'deviceMetrics' in node:
                uptime_hours = node['deviceMetrics'].get('uptimeSeconds', 0) / 3600
                self._previous_uptimes[node_id] = uptime_hours
        
        print(f"Saved data for {len(csv_rows)} nodes at {timestamp_str}")
    
    def get_battery_history(self, days: float = 7) -> pd.DataFrame:
        """
        Get battery history data for the specified time period.
        
        Args:
            days: Number of days (or fractional days for hours) to look back
            
        Returns:
            DataFrame with battery history data
        """
        if not os.path.exists(self.csv_file):
            return pd.DataFrame()
        
        try:
            # Read CSV data
            df = pd.read_csv(self.csv_file)
            
            if df.empty:
                return df
            
            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Filter to last N days
            cutoff_date = datetime.now() - timedelta(days=days)
            print(f"DEBUG: Filtering data from {cutoff_date} onwards")
            df = df[df['timestamp'] >= cutoff_date]
            print(f"DEBUG: Data shape after time filtering: {df.shape}")
            
            # Sort by timestamp
            df = df.sort_values('timestamp')
            
            # Ensure we have data points even if sparse
            # This helps with chart visualization
            if not df.empty:
                # Add a small buffer to show the full timespan
                df = df.reset_index(drop=True)
            
            return df
            
        except Exception as e:
            print(f"Error reading battery history: {e}")
            return pd.DataFrame()
    
    def get_node_battery_history(self, node_id: str, days: float = 7) -> pd.DataFrame:
        """
        Get battery history for a specific node.
        
        Args:
            node_id: Node ID to get history for
            days: Number of days (or fractional days for hours) to look back
            
        Returns:
            DataFrame with battery history for the specific node
        """
        df = self.get_battery_history(days)
        if df.empty:
            return df
        
        return df[df['node_id'] == node_id].copy()
    
    def get_latest_data(self) -> Optional[Dict[str, Any]]:
        """
        Get the most recent data snapshot.
        
        Returns:
            Dictionary with latest node data or None if no data exists
        """
        if not os.path.exists(self.json_file):
            return None
        
        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if lines:
                    # Get the last line (most recent data)
                    latest_data = json.loads(lines[-1].strip())
                    return latest_data
        except Exception as e:
            print(f"Error reading latest data: {e}")
        
        return None
    
    def cleanup_old_data(self, days_to_keep: int = 30) -> None:
        """
        Clean up old data files to prevent them from growing too large.
        
        Args:
            days_to_keep: Number of days of data to keep
        """
        try:
            df = self.get_battery_history(days_to_keep * 2)  # Get more data than needed
            if df.empty:
                return
            
            # Get the cutoff timestamp
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            # Filter data to keep
            df_to_keep = df[df['timestamp'] >= cutoff_date]
            
            # Write back the filtered data
            df_to_keep.to_csv(self.csv_file, index=False)
            
            print(f"Cleaned up data older than {days_to_keep} days")
            
        except Exception as e:
            print(f"Error cleaning up old data: {e}")
    
    def get_data_summary(self) -> Dict[str, Any]:
        """
        Get a summary of stored data.
        
        Returns:
            Dictionary with data summary statistics
        """
        try:
            df = self.get_battery_history(30)  # Get last 30 days
            
            if df.empty:
                return {
                    'total_records': 0,
                    'unique_nodes': 0,
                    'date_range': None,
                    'latest_timestamp': None
                }
            
            summary = {
                'total_records': len(df),
                'unique_nodes': df['node_id'].nunique(),
                'date_range': {
                    'start': df['timestamp'].min().isoformat(),
                    'end': df['timestamp'].max().isoformat()
                },
                'latest_timestamp': df['timestamp'].max().isoformat()
            }
            
            return summary
            
        except Exception as e:
            print(f"Error getting data summary: {e}")
            return {
                'total_records': 0,
                'unique_nodes': 0,
                'date_range': None,
                'latest_timestamp': None
            }

"""
Data persistence module for storing node data and battery history.
"""
import csv
import json
import os
import time
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import pandas as pd

class DataPersistence:
    """Handles data persistence for node metrics and battery history (local filesystem)."""

    def __init__(self, data_dir: str = "data", backend: str = "local", s3_bucket: Optional[str] = None, s3_prefix: str = ""):
        """
        Initialize the data persistence manager.

        Args:
            data_dir: Directory to store data files (used for local backend and as temp workspace for S3)
            backend: 'local' or 's3'
            s3_bucket: S3 bucket name when using S3 backend
            s3_prefix: Optional prefix (folder) within the S3 bucket
        """
        self.backend = (backend or "local")
        self.data_dir = data_dir
        if self.backend != 'local':
            print(f"Warning: requested backend '{self.backend}' is not supported; falling back to local filesystem")
            self.backend = 'local'

        # Local file paths (used for local backend and as temp files for S3)
        self.csv_file = os.path.join(data_dir, "node_data.csv")
        self.json_file = os.path.join(data_dir, "node_data.json")
        self.neighbour_packets_file = os.path.join(data_dir, "neighbour_packets.json")
        self.reporter_aliases_file = os.path.join(data_dir, "reporter_aliases.json")
        self.reporter_visibility_file = os.path.join(data_dir, "reporter_visibility.json")

        # Ensure data directory exists
        os.makedirs(data_dir, exist_ok=True)

        # Initialize CSV file with headers if it doesn't exist
        self._initialize_csv()

        # Track previous uptime values to detect changes
        self._previous_uptimes = {}
        # Track previous last-heard values so MQTT-only updates persist even when uptime is unchanged
        self._previous_last_heard = {}

        # Load previous uptime values from existing data
        self._load_previous_uptimes()

    # ---- Generic helpers (local filesystem only) ----
    def _read_csv(self) -> pd.DataFrame:
        """Return a DataFrame loaded from local CSV (or empty DataFrame)."""
        if not os.path.exists(self.csv_file):
            return pd.DataFrame()
        try:
            try:
                return pd.read_csv(self.csv_file, on_bad_lines='skip')
            except TypeError:
                return pd.read_csv(self.csv_file, error_bad_lines=False)
        except Exception as e:
            print(f"Error reading CSV: {e}")
            return pd.DataFrame()

    def _append_to_csv_rows(self, rows: list[list]) -> None:
        if not rows:
            return
        with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(rows)

    def _append_to_ndjson(self, obj: Any) -> None:
        """Append a JSON object as newline-delimited JSON to node_data.json (local)."""
        line = json.dumps(obj) + '\n'
        with open(self.json_file, 'a', encoding='utf-8') as f:
            f.write(line)

    def _read_json_file(self, filename: str) -> Optional[Any]:
        """Read a JSON file (full JSON object) from local filesystem and return parsed object."""
        path = os.path.join(self.data_dir, filename)
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading JSON {path}: {e}")
            return None

    def _write_json_file(self, filename: str, obj: Any) -> None:
        path = os.path.join(self.data_dir, filename)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(obj, f, indent=2)
        except Exception as e:
            print(f"Error writing JSON {path}: {e}")

    def _read_ndjson_lines(self) -> list[str]:
        """Return list of lines from node_data.json (ndjson) or empty list (local)."""
        if not os.path.exists(self.json_file):
            return []
        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                return f.readlines()
        except Exception as e:
            print(f"Error reading ndjson {self.json_file}: {e}")
            return []
    
    def _initialize_csv(self) -> None:
        """Initialize CSV file with headers if it doesn't exist."""
        headers = [
            'timestamp', 'node_id', 'short_name', 'long_name', 'hw_model',
            'battery_level', 'voltage', 'is_charging', 'uptime_hours',
            'channel_utilization', 'last_heard', 'is_favorite',
            'co2', 'co2_temperature', 'co2_humidity'
        ]

        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
    
    def _load_previous_uptimes(self) -> None:
        """Load the most recent uptime values for each node from existing data."""
        df = self._read_csv()
        if df.empty:
            return

        try:
            latest_data = df.groupby('node_id')['uptime_hours'].last()
            self._previous_uptimes = latest_data.to_dict()

            latest_last_heard = df.groupby('node_id')['last_heard'].last()
            self._previous_last_heard = latest_last_heard.to_dict()
        except Exception as e:
            print(f"Warning: Could not load previous uptime values: {e}")
            self._previous_uptimes = {}
            self._previous_last_heard = {}
    
    def save_nodes_data(self, nodes_data: Dict[str, Dict[str, Any]]) -> None:
        """
        Save current nodes data to both CSV and JSON files.
        
        Args:
            nodes_data: Dictionary of node data keyed by node ID
        """
        timestamp = int(time.time())
        timestamp_str = datetime.fromtimestamp(timestamp).isoformat()
        
        # CSV history is rate-limited, but JSON snapshots should still be written
        # so MQTT-only/non-telemetry nodes survive restarts.
        skip_csv_write = False

        # Check if we already have recent CSV data to avoid duplicates
        try:
            existing_df = self._read_csv()
            if not existing_df.empty:
                existing_df['timestamp'] = pd.to_datetime(existing_df['timestamp'])
                if not existing_df['timestamp'].empty:
                    latest_existing_ts = existing_df['timestamp'].max()
                    current_ts = pd.to_datetime(timestamp_str)
                    time_diff = (current_ts - latest_existing_ts).total_seconds()
                    if time_diff < 240:
                        print(f"Data for timestamp {timestamp_str} is less than 4 minutes after previous ({latest_existing_ts}), skipping save")
                        skip_csv_write = True
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
            user_info = node.get('user', {})
            short_name = user_info.get('shortName', 'Unknown')
            long_name = user_info.get('longName', 'Unknown')
            hw_model = user_info.get('hwModel', 'Unknown')
            is_favorite = 'isFavorite' in node
            last_heard = int(node.get('lastHeard', 0) or 0)

            # JSON snapshot stores the latest known state for all nodes, even if they
            # don't have telemetry/device metrics yet.
            json_node = {
                'user': {
                    'shortName': short_name,
                    'longName': long_name,
                    'hwModel': hw_model,
                },
                'lastHeard': last_heard,
                'isFavorite': is_favorite,
            }
            if 'deviceMetrics' in node:
                json_node['deviceMetrics'] = dict(node.get('deviceMetrics') or {})
            if 'mqtt_topic' in node:
                json_node['mqtt_topic'] = node.get('mqtt_topic')
            if '_is_bridge' in node:
                json_node['_is_bridge'] = bool(node.get('_is_bridge'))
            if 'position' in node:
                json_node['position'] = node.get('position')
            json_data['nodes'][node_id] = json_node

            # Skip CSV history rows for nodes without device metrics
            if 'deviceMetrics' not in node:
                continue
                
            # Extract uptime and check if it has changed
            uptime_hours = node['deviceMetrics'].get('uptimeSeconds', 0) / 3600
            previous_uptime = self._previous_uptimes.get(node_id, 0)
            previous_last_heard = int(self._previous_last_heard.get(node_id, 0) or 0)
            
            print(f"watchme: {uptime_hours}, {previous_uptime}")
            # Skip nodes that haven't changed their uptime (indicating they haven't updated telemetry.
            # Allow small float precision differences and optionally a force-write override in the future
            uptime_diff = abs(float(uptime_hours) - float(previous_uptime))
            last_heard_changed = last_heard > previous_last_heard
            # Consider uptime the "same" if the change is less than 0.01 hour (36 seconds)
            if skip_csv_write or (uptime_diff < 0.01 and not last_heard_changed):
                print(f'skipping writing to db for node {node_id} (uptime difference {uptime_diff:.4f} < 0.0001 and lastHeard unchanged)')
                continue
            else:
                print(f' writing to db for node {node_id} (uptime difference {uptime_diff:.4f}, lastHeard changed={last_heard_changed})')            # Extract battery information
            battery_level = node['deviceMetrics'].get('batteryLevel', 0)
            voltage = node['deviceMetrics'].get('voltage', 0.0)
            is_charging = battery_level == 101
            
            # Extract other metrics
            channel_util = node['deviceMetrics'].get('channelUtilization', 0.0)
            
            # Extract telemetry fields
            co2 = node['deviceMetrics'].get('co2', None)
            co2_temperature = node['deviceMetrics'].get('co2Temperature', None)
            co2_humidity = node['deviceMetrics'].get('co2Humidity', None)
            
            # CSV row
            csv_row = [
                timestamp_str, node_id, short_name, long_name, hw_model,
                battery_level, voltage, is_charging, uptime_hours,
                channel_util, last_heard, is_favorite,
                co2, co2_temperature, co2_humidity
            ]
            csv_rows.append(csv_row)
        
        # Write to CSV
        if csv_rows:
            self._append_to_csv_rows(csv_rows)

        # Write to JSON (append to file with timestamp)
        self._append_to_ndjson(json_data)
        
        # Update the previous uptime tracking for saved nodes
        for node_id, node in nodes_data.items():
            if 'deviceMetrics' in node and not skip_csv_write:
                uptime_hours = node['deviceMetrics'].get('uptimeSeconds', 0) / 3600
                self._previous_uptimes[node_id] = uptime_hours
                self._previous_last_heard[node_id] = int(node.get('lastHeard', 0) or 0)
        
        print(f"Saved data for {len(csv_rows)} nodes at {timestamp_str}")
    
    def get_battery_history(self, days: float = 7) -> pd.DataFrame:
        """
        Get battery history data for the specified time period.
        
        Args:
            days: Number of days (or fractional days for hours) to look back
            
        Returns:
            DataFrame with battery history data
        """
        df = self._read_csv()
        try:
            if df.empty:
                return df
            
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
            traceback.print_exc()
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
    
    def get_telemetry_history(self, days: float = 7) -> pd.DataFrame:
        """
        Get telemetry history data (CO2, temperature, humidity) for the specified time period.
        
        Args:
            days: Number of days (or fractional days for hours) to look back
            
        Returns:
            DataFrame with telemetry history data
        """
        if not os.path.exists(self.csv_file):
            return pd.DataFrame()
        
        try:
            # Read CSV data with error handling for inconsistent field counts
            try:
                # Try modern pandas syntax first (>=1.3)
                df = pd.read_csv(self.csv_file, on_bad_lines='skip')
            except TypeError:
                # Fallback for older pandas versions
                df = pd.read_csv(self.csv_file, error_bad_lines=False)
            
            if df.empty:
                return df
            
            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Filter to last N days
            cutoff_date = datetime.now() - timedelta(days=days)
            df = df[df['timestamp'] >= cutoff_date]
            
            # Filter out rows with no telemetry data
            df = df.dropna(subset=['co2', 'co2_temperature', 'co2_humidity'], how='all')
            
            # Sort by timestamp
            df = df.sort_values('timestamp')
            
            return df
            
        except Exception as e:
            print(f"Error reading telemetry history: {e}")
            traceback.print_exc()
            return pd.DataFrame()
    
    def get_node_telemetry_history(self, node_id: str, days: float = 7) -> pd.DataFrame:
        """
        Get telemetry history for a specific node.
        
        Args:
            node_id: Node ID to get history for
            days: Number of days (or fractional days for hours) to look back
            
        Returns:
            DataFrame with telemetry history for the specific node
        """
        df = self.get_telemetry_history(days)
        if df.empty:
            return df
        
        return df[df['node_id'] == node_id].copy()
    
    def get_last_known_nodes(self) -> Dict[str, Any]:
        """
        Reconstruct the most-recent known state for every node from the CSV.
        Returns a dict keyed by node_id in the same shape used by MqttConnectionManager.
        """
        nodes: Dict[str, Any] = {}

        latest_snapshot = self.get_latest_data()
        if latest_snapshot and isinstance(latest_snapshot.get('nodes'), dict):
            for node_id, node in latest_snapshot['nodes'].items():
                restored = dict(node)
                restored['_from_persistence'] = True
                nodes[str(node_id)] = restored

        df = self._read_csv()
        if df.empty:
            return nodes
        try:

            # Keep only the latest row per node
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            latest = df.groupby('node_id').last().reset_index()

            for _, row in latest.iterrows():
                node_id = str(row['node_id'])
                battery_level = int(row.get('battery_level', 0) or 0)
                voltage = float(row.get('voltage', 0.0) or 0.0)
                uptime_hours = float(row.get('uptime_hours', 0.0) or 0.0)
                channel_util = float(row.get('channel_utilization', 0.0) or 0.0)
                last_heard = int(row.get('last_heard', 0) or 0)
                existing = nodes.get(node_id, {})
                existing_user = dict(existing.get('user') or {})
                existing_user.update({
                    'shortName': str(row.get('short_name', existing_user.get('shortName', node_id[-4:])) or node_id[-4:]),
                    'longName': str(row.get('long_name', existing_user.get('longName', node_id)) or node_id),
                    'hwModel': str(row.get('hw_model', existing_user.get('hwModel', 'Unknown')) or 'Unknown'),
                })
                existing_metrics = dict(existing.get('deviceMetrics') or {})
                existing_metrics.update({
                    'batteryLevel': battery_level,
                    'voltage': voltage,
                    'uptimeSeconds': int(uptime_hours * 3600),
                    'channelUtilization': channel_util,
                })
                nodes[node_id] = {
                    **existing,
                    'user': existing_user,
                    'deviceMetrics': existing_metrics,
                    'lastHeard': max(int(existing.get('lastHeard', 0) or 0), last_heard),
                    '_from_persistence': True,
                }
            print(f"Loaded {len(nodes)} nodes from persistence")
            return nodes
        except Exception as e:
            print(f"Warning: Could not load last known nodes: {e}")
            return nodes

    def save_neighbour_packets(self, packets: list[Dict[str, Any]]) -> None:
        """Persist collected neighbour packets so they survive app restarts."""
        try:
            deduped_packets = []
            seen = set()
            for packet in packets:
                reporter = packet.get('payload', {}).get('node_id', packet.get('from'))
                timestamp = int(packet.get('timestamp', 0) or 0)
                canonical = json.dumps(packet, sort_keys=True, separators=(',', ':'))
                key = (str(reporter), timestamp, canonical)
                if key in seen:
                    continue
                seen.add(key)
                deduped_packets.append(packet)
            to_save = deduped_packets[-5000:]
            count_to_save = len(to_save)
            print(f"DEBUG: Saving {count_to_save} deduplicated neighbour packets")
            self._write_json_file('neighbour_packets.json', to_save)
            print(f"DEBUG: Successfully saved {count_to_save} neighbour packets")
        except Exception as e:
            print(f"Warning: Could not save neighbour packets: {e}")

    def get_neighbour_packets(self) -> list[Dict[str, Any]]:
        """Load persisted neighbour packets."""
        try:
            data = self._read_json_file('neighbour_packets.json')
            if not isinstance(data, list):
                return []
            print(f"DEBUG: Loaded {len(data)} neighbour packets")
            deduped_packets = []
            seen = set()
            for packet in data:
                reporter = packet.get('payload', {}).get('node_id', packet.get('from'))
                timestamp = int(packet.get('timestamp', 0) or 0)
                canonical = json.dumps(packet, sort_keys=True, separators=(',', ':'))
                key = (str(reporter), timestamp, canonical)
                if key in seen:
                    continue
                seen.add(key)
                deduped_packets.append(packet)
            print(f"DEBUG: After deduplication, {len(deduped_packets)} neighbour packets")
            return deduped_packets
        except Exception as e:
            print(f"Warning: Could not load neighbour packets: {e}")
            return []

    def save_reporter_aliases(self, aliases: Dict[str, str]) -> None:
        """Persist reporter-node nickname mappings."""
        try:
            clean_aliases: Dict[str, str] = {}
            for reporter, alias in (aliases or {}).items():
                key = str(reporter or '').strip()
                value = str(alias or '').strip()
                if not key or not value:
                    continue
                clean_aliases[key] = value
            self._write_json_file('reporter_aliases.json', clean_aliases)
        except Exception as e:
            print(f"Warning: Could not save reporter aliases: {e}")

    def get_reporter_aliases(self) -> Dict[str, str]:
        """Load reporter-node nickname mappings."""
        try:
            data = self._read_json_file('reporter_aliases.json')
            if not isinstance(data, dict):
                return {}
            aliases: Dict[str, str] = {}
            for reporter, alias in data.items():
                key = str(reporter or '').strip()
                value = str(alias or '').strip()
                if key and value:
                    aliases[key] = value
            return aliases
        except Exception as e:
            print(f"Warning: Could not load reporter aliases: {e}")
            return {}

    def save_reporter_visibility(self, visibility: Dict[str, bool]) -> None:
        """Persist reporter-node visibility mappings."""
        try:
            clean_visibility: Dict[str, bool] = {}
            for reporter, visible in (visibility or {}).items():
                key = str(reporter or '').strip()
                if not key:
                    continue
                clean_visibility[key] = bool(visible)
            self._write_json_file('reporter_visibility.json', clean_visibility)
        except Exception as e:
            print(f"Warning: Could not save reporter visibility: {e}")

    def get_reporter_visibility(self) -> Dict[str, bool]:
        """Load reporter-node visibility mappings."""
        try:
            data = self._read_json_file('reporter_visibility.json')
            if not isinstance(data, dict):
                return {}
            visibility: Dict[str, bool] = {}
            for reporter, visible in data.items():
                key = str(reporter or '').strip()
                if key:
                    visibility[key] = bool(visible)
            return visibility
        except Exception as e:
            print(f"Warning: Could not load reporter visibility: {e}")
            return {}

    def get_latest_data(self) -> Optional[Dict[str, Any]]:
        """
        Get the most recent data snapshot.
        
        Returns:
            Dictionary with latest node data or None if no data exists
        """
        try:
            lines = self._read_ndjson_lines()
            if lines:
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

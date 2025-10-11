"""
Meshtastic interface module for handling network connections and node data.
"""
from typing import List, Dict, Any, Optional
import time

class MeshInterface:
    """Interface for interacting with Meshtastic network nodes."""
    
    def __init__(self, interface):
        """
        Initialize the MeshInterface.
        
        Args:
            interface: Meshtastic interface (TCP or Serial)
        """
        self.number = 1
        self.interface = interface
        self.last_heard_cache = {}  # Cache to track lastHeard changes

    def get_uptime(self, node: Dict[str, Any], asString: bool = True) -> Any:
        """
        Get uptime in hours for a node.

        Args:
            node: Node data dictionary
            asString (bool, optional): If True, return formatted string. If False, return uptime as float.

        Returns:
            float or str: Uptime in hours (float) or as a formatted string if asString is True.
        """
        uptime_hours = node['deviceMetrics']['uptimeSeconds'] / 3600
        
        return f"up {uptime_hours:4.1f} hrs" if asString else uptime_hours


    def get_last_heard_delta(self, node: Dict[str, Any], asString: bool = True) -> Any:
        """
        Get time delta in seconds since node was last heard.

        Args:
            node: Node data dictionary
            asString (bool, optional): If True, return formatted string. If False, return delta as int (seconds).

        Returns:
            int or str: Delta in seconds (int) or formatted string if asString is True.
        """
        lastHeard = node.get('lastHeard', 0)
        now = int(time.time())
        delta = now - lastHeard
        if delta < 0:
            delta = 0
        if asString:
            hours = delta // 3600
            minutes = (delta % 3600) // 60
            seconds = delta % 60
            timeAgo = f"{hours:02}:{minutes:02}:{seconds:02}"
            return f"last heard T-{timeAgo} Ago"
        else:
            return delta

    def get_last_heard(self, node: Dict[str, Any], asString: bool = True) -> Any:
        """
        Get the timestamp string for when the node was last heard, or the raw lastHeard value.

        Args:
            node: Node data dictionary
            asString (bool, optional): If True, return formatted string. If False, return raw lastHeard value.

        Returns:
            str or int: Formatted last heard timestamp string or raw lastHeard epoch time.
        """
        lastHeard = node.get('lastHeard', 0)
        if asString:
            now = int(time.time())
            delta = now - lastHeard
            if delta > 6 * 3600:
                last_heard_str = time.strftime("%H:%M %d/%m/%Y", time.localtime(lastHeard))
            else:
                last_heard_str = time.strftime("%H:%M", time.localtime(lastHeard))
            return f"RX'd {last_heard_str}"
        else:
            return lastHeard

    def get_single_node_dump(self):
        node_ids = list(self.interface.nodes.keys())
        if node_ids:
            node_id = node_ids[0]
        else:
            return
        node = self.interface.nodes[node_id]
        node_keys = node.keys()
        print("Single node dump:")
        print(node_keys)
        print()
        print(node)

        return(node)        


    def get_node_battery_status(self, node: Dict[str, Any], asString: bool = True) -> Any:
        """
        Get battery information for a node, either formatted as a string or as the raw data.

        Args:
            node: Node data dictionary
            asString (bool, optional): If True, return formatted string. If False, return (battery_level, voltage, is_charging) tuple.

        Returns:
            str or tuple: Formatted battery string or (battery_level, voltage, is_charging) tuple
        """
        battery_level = node['deviceMetrics']['batteryLevel']
        voltage = node['deviceMetrics']['voltage']
        is_charging = battery_level == 101

        if asString:
            if is_charging:
                out_str = " Chg"
            else:
                out_str = f"{battery_level:3}%"
            out_str += f", {voltage:.3f}V "
            return out_str
        else:
            return battery_level, voltage, is_charging

    def print_mesh_metrics(self, whole_mesh: bool = False) -> None:
        """
        Print battery information for nodes.
        
        Args:
            whole_mesh: If True, show all nodes with device metrics
        """
        for node_id in self.interface.nodes:
            node = self.interface.nodes[node_id]
            node_keys = node.keys()
            
            if whole_mesh and "deviceMetrics" in node_keys:
                print(f"{node_id}  {node['user']['longName']:25} - {node['user']['hwModel']:21} : {self.get_node_battery_status(node)} : {self.get_last_heard(node)} - {self.get_uptime(node)}")
            elif "isFavorite" in node_keys:
                print(f"{node_id}  {node['user']['longName']:25} - {node['user']['hwModel']:21} : {self.get_node_battery_status(node)} : {self.get_last_heard(node)} - {self.get_uptime(node)}")

    def find_non_favorites_string(self) -> None:
        """Print nodes that are not marked as favorites."""
        for node_id in self.interface.nodes:
            node = self.interface.nodes[node_id]
            node_keys = node.keys()
            
            if "isFavorite" not in node_keys:
                print(f"{node_id}  {node['user']['longName']:20} - {node['user']['hwModel']:15}")

    def find_non_favorites(self) -> List[Dict[str, Any]]:
        """
        Find nodes that are not marked as favorites.
        
        Returns:
            List of non-favorite node dictionaries
        """
        nodes = []
        for node_id in self.interface.nodes:
            node = self.interface.nodes[node_id]
            node_keys = node.keys()
            
            if "isFavorite" not in node_keys:
                print(f"{node_id}  {node['user']['longName']:20} - {node['user']['hwModel']:15}")
                nodes.append(node)
        return nodes

    def find_favorites(self) -> List[Dict[str, Any]]:
        """
        Find nodes that are marked as favorites.
        
        Returns:
            List of favorite node dictionaries
        """
        nodes = []
        for node_id in self.interface.nodes:
            node = self.interface.nodes[node_id]
            node_keys = node.keys()
            
            if "isFavorite" in node_keys:
                print(f"{node_id}  {node['user']['longName']:20} - {node['user']['hwModel']:15}")
                nodes.append(node)
        return nodes

    def get_all_nodes_data(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all nodes data from the interface.
        
        Returns:
            Dictionary of node data keyed by node ID
        """
        return self.interface.nodes

    def get_node_data(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        Get data for a specific node.
        
        Args:
            node_id: The node ID to get data for
            
        Returns:
            Node data dictionary or None if not found
        """
        return self.interface.nodes.get(node_id)

    def refresh_nodes_data(self) -> None:
        """
        Refresh the nodes data by requesting updated information from the network.
        This forces the interface to update its internal nodes dictionary with fresh data.
        """
        try:
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            print(f"DEBUG [{timestamp}]: Attempting to refresh nodes data...")
            
            # Try multiple methods to force data refresh
            refresh_methods = [
                'requestNodeInfo',
                'refreshNodes', 
                'sendHeartbeat',
                'sendTelemetry',
                'showNodes'
            ]
            
            for method_name in refresh_methods:
                if hasattr(self.interface, method_name):
                    try:
                        method = getattr(self.interface, method_name)
                        if callable(method):
                            print(f"DEBUG [{timestamp}]: Calling {method_name}()")
                            if method_name in ['requestNodeInfo', 'refreshNodes']:
                                # These methods might need parameters
                                if method_name == 'requestNodeInfo':
                                    # Try to request info for all known nodes
                                    for node_id in list(self.interface.nodes.keys()):
                                        try:
                                            method(node_id)
                                        except:
                                            pass
                                else:
                                    method()
                            else:
                                method()
                            break  # If one method works, don't try others
                    except Exception as e:
                        print(f"DEBUG [{timestamp}]: {method_name} failed: {e}")
                        continue
            
            # Small delay to allow for network response
            time.sleep(0.2)
            
            # Check if we have any methods that might trigger a data refresh
            if hasattr(self.interface, '_handleFromRadio'):
                print(f"DEBUG [{timestamp}]: Interface has _handleFromRadio method")
                
        except Exception as e:
            # If refresh fails, continue with existing data
            print(f"Warning: Failed to refresh nodes data: {e}")
    
    def force_last_heard_update(self) -> None:
        """
        Force update of lastHeard timestamps by checking for recent packets.
        This is a workaround for when the Meshtastic library doesn't automatically
        update lastHeard timestamps in the nodes dictionary.
        """
        try:
            current_time = int(time.time())
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            
            # Debug: Print current lastHeard values before any updates
            print(f"DEBUG [{timestamp}]: Checking lastHeard timestamps...")
            for node_id, node in self.interface.nodes.items():
                if 'lastHeard' in node:
                    last_heard_time = time.strftime("%H:%M:%S", time.localtime(node['lastHeard']))
                    node_short = node_id[-4:] if len(node_id) >= 4 else node_id
                    delta = current_time - node['lastHeard']
                    print(f"DEBUG [{timestamp}]: Node ...{node_short}: lastHeard={last_heard_time} (T-{delta}s)")
            
            # Check if interface has a way to get recent packets
            if hasattr(self.interface, 'getRecentPackets'):
                recent_packets = self.interface.getRecentPackets()
                for packet in recent_packets:
                    if 'from' in packet and 'rx_time' in packet:
                        node_id = packet['from']
                        if node_id in self.interface.nodes:
                            # Update the lastHeard timestamp
                            self.interface.nodes[node_id]['lastHeard'] = packet['rx_time']
            
            # Alternative: try to get node info for all known nodes
            elif hasattr(self.interface, 'getNodeInfo'):
                for node_id in list(self.interface.nodes.keys()):
                    try:
                        node_info = self.interface.getNodeInfo(node_id)
                        if node_info and 'lastHeard' in node_info:
                            self.interface.nodes[node_id]['lastHeard'] = node_info['lastHeard']
                    except:
                        # If we can't get info for a specific node, continue
                        pass
                        
        except Exception as e:
            print(f"Warning: Failed to force last heard update: {e}")
    
    def detect_last_heard_changes(self) -> None:
        """
        Detect changes in lastHeard timestamps by comparing with cached values.
        This method monitors the interface.nodes dictionary for updates.
        """
        try:
            current_time = int(time.time())
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            changes_detected = False
            
            for node_id, node in self.interface.nodes.items():
                if 'lastHeard' in node:
                    current_last_heard = node['lastHeard']
                    cached_last_heard = self.last_heard_cache.get(node_id)
                    
                    # Check if the lastHeard timestamp has changed
                    if cached_last_heard is None or cached_last_heard != current_last_heard:
                        node_short = node_id[-4:] if len(node_id) >= 4 else node_id
                        last_heard_time = time.strftime("%H:%M:%S", time.localtime(current_last_heard))
                        
                        if cached_last_heard is not None:
                            # This is an update, not initial cache
                            print(f"DEBUG [{timestamp}]: lastHeard updated for node ...{node_short}: {last_heard_time}")
                            changes_detected = True
                        
                        # Update the cache
                        self.last_heard_cache[node_id] = current_last_heard
            
            if not changes_detected:
                print(f"DEBUG [{timestamp}]: No lastHeard changes detected")
                
        except Exception as e:
            print(f"Warning: Failed to detect last heard changes: {e}")
    

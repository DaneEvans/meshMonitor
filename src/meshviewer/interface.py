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

    def get_uptime_string(self, node: Dict[str, Any]) -> str:
        """
        Get formatted uptime string for a node.
        
        Args:
            node: Node data dictionary
            
        Returns:
            Formatted uptime string
        """
        uptime_hours = node['deviceMetrics']['uptimeSeconds'] / 3600
        return f"up {uptime_hours:4.1f} hrs"

    def get_last_heard_delta_string(self, node: Dict[str, Any]) -> str:
        """
        Get formatted uptime string for a node.
        
        Args:
            node: Node data dictionary
            
        Returns:
            Formatted uptime string
        """
        lastHeard = node['lastHeard']
        # Convert lastHeard (epoch seconds) to "time ago" string (hh:mm:ss)
        now = int(time.time())
        delta = now - lastHeard
        if delta < 0:
            # Future time, just show 0
            delta = 0
        hours = delta // 3600
        minutes = (delta % 3600) // 60
        seconds = delta % 60
        timeAgo = f"{hours:02}:{minutes:02}:{seconds:02}"
        return f"last heard T-{timeAgo} Ago"

    def get_last_heard_string(self, node: Dict[str, Any]) -> str:
        """
        Get the timestamp string for when the node was last heard.

        Args:
            node: Node data dictionary

        Returns:
            Formatted last heard timestamp string
        """
        lastHeard = node['lastHeard']
        # Convert lastHeard (epoch seconds) to human-readable time
        now = int(time.time())
        delta = now - lastHeard
        if delta > 6 * 3600:
            last_heard_str = time.strftime("%H:%M %d/%m/%Y", time.localtime(lastHeard))
        else:
            last_heard_str = time.strftime("%H:%M", time.localtime(lastHeard))
        return f"RX'd {last_heard_str}"

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


    def get_battery_levels(self, node: Dict[str, Any]) -> str:
        """
        Get formatted battery information for a node.
        
        Args:
            node: Node data dictionary
            
        Returns:
            Formatted battery string
        """
        is_charging = node['deviceMetrics']['batteryLevel'] == 101
        out_str = ""
        
        if is_charging:
            out_str += " Chg"
        else:
            out_str += f"{node['deviceMetrics']['batteryLevel']:3}%"
        
        out_str += f", {node['deviceMetrics']['voltage']:.3f}V "
        return out_str

    def get_battery_string(self, whole_mesh: bool = False) -> None:
        """
        Print battery information for nodes.
        
        Args:
            whole_mesh: If True, show all nodes with device metrics
        """
        for node_id in self.interface.nodes:
            node = self.interface.nodes[node_id]
            node_keys = node.keys()
            
            if whole_mesh and "deviceMetrics" in node_keys:
                print(f"{node_id}  {node['user']['longName']:25} - {node['user']['hwModel']:21} : {self.get_battery_levels(node)} : {self.get_last_heard_string(node)} - {self.get_uptime_string(node)}")
            elif "isFavorite" in node_keys:
                print(f"{node_id}  {node['user']['longName']:25} - {node['user']['hwModel']:21} : {self.get_battery_levels(node)} : {self.get_last_heard_string(node)} - {self.get_uptime_string(node)}")

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

"""
Main GUI module for MeshViewer using NiceGUI.
"""
from nicegui import ui
from typing import Optional, Dict, Any
from meshviewer.connection import MeshConnectionManager
from meshviewer.interface import MeshInterface


class MeshViewerGUI:
    """Main GUI class for the MeshViewer application."""
    
    def __init__(self):
        """Initialize the GUI."""
        self.connection_manager = MeshConnectionManager()
        self.mesh_interface: Optional[MeshInterface] = None
        self.connected = False
        self.show_all_nodes = False
        self.nodes_data: Dict[str, Any] = {}
        
        # UI components (initialized in setup_ui)
        self.tcp_host = None
        self.tcp_port = None
        self.serial_port = None
        self.connection_status = None
        self.show_all_toggle = None
        self.nodes_container = None
        self.refresh_nodes_button = None
        
    def setup_ui(self) -> None:
        """Setup the main UI components."""
        ui.page_title("MeshViewer - Meshtastic Network Monitor")
        
        with ui.header().classes('items-center justify-between'):
            ui.label('MeshViewer').classes('text-h4')
            ui.label('Meshtastic Network Monitor').classes('text-subtitle2')
        
        with ui.row().classes('w-full'):
            with ui.column().classes('w-1/3'):
                self._setup_connection_panel()
            
            with ui.column().classes('w-2/3'):
                self._setup_nodes_panel()
    
    def _setup_connection_panel(self) -> None:
        """Setup the connection control panel."""
        with ui.card().classes('w-full'):
            ui.label('Connection').classes('text-h6')
            
            with ui.row().classes('w-full'):
                self.tcp_host = ui.input('TCP Host', value='192.168.0.114').classes('flex-1')
                self.tcp_port = ui.number('Port', value=4403).classes('w-20')
            
            with ui.row().classes('w-full'):
                self.serial_port = ui.input('Serial Port (optional)').classes('flex-1')
            
            with ui.row().classes('w-full gap-2'):
                ui.button('Connect TCP', on_click=self.connect_tcp).classes('flex-1')
                ui.button('Connect Serial', on_click=self.connect_serial).classes('flex-1')
                ui.button('Disconnect', on_click=self.disconnect).classes('flex-1').bind_visibility_from(self, 'connected')
            
            self.connection_status = ui.label('Disconnected').classes('text-caption')
    
    def _setup_nodes_panel(self) -> None:
        """Setup the nodes display panel."""
        with ui.card().classes('w-full'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label('Network Nodes').classes('text-h6')
                self.show_all_toggle = ui.checkbox('Show All Nodes', value=False).bind_value(self, 'show_all_nodes')
            
            self.nodes_container = ui.column().classes('w-full')
            self.refresh_nodes_button = ui.button('Refresh', on_click=self.refresh_nodes).bind_visibility_from(self, 'connected')
    
    def connect_tcp(self) -> None:
        """Connect via TCP."""
        host = self.tcp_host.value
        port = int(self.tcp_port.value)
        
        if self.connection_manager.connect_tcp(host, port):
            self.mesh_interface = MeshInterface(self.connection_manager.get_interface())
            self.connected = True
            self.connection_status.text = f'Connected via TCP to {host}:{port}'
            self.connection_status.classes('text-green')
            self.refresh_nodes()
        else:
            self.connection_status.text = 'TCP connection failed'
            self.connection_status.classes('text-red')
    
    def connect_serial(self) -> None:
        """Connect via Serial."""
        port = self.serial_port.value if self.serial_port.value else None
        
        if self.connection_manager.connect_serial(port):
            self.mesh_interface = MeshInterface(self.connection_manager.get_interface())
            self.connected = True
            port_display = port or 'auto-detected'
            self.connection_status.text = f'Connected via Serial on {port_display}'
            self.connection_status.classes('text-green')
            self.refresh_nodes()
        else:
            self.connection_status.text = 'Serial connection failed'
            self.connection_status.classes('text-red')
    
    def disconnect(self) -> None:
        """Disconnect from the network."""
        self.connection_manager.disconnect()
        self.mesh_interface = None
        self.connected = False
        self.connection_status.text = 'Disconnected'
        self.connection_status.classes('text-gray')
        self._clear_nodes_display()
    
    def refresh_nodes(self) -> None:
        """Refresh the nodes display."""
        if not self.connected or not self.mesh_interface:
            return
        
        self.nodes_data = self.mesh_interface.get_all_nodes_data()
        self._update_nodes_display()
    
    def _update_nodes_display(self) -> None:
        """Update the nodes display with current data."""
        self.nodes_container.clear()
        
        if not self.nodes_data:
            with self.nodes_container:
                ui.label('No nodes found').classes('text-gray-500')
            return
        
        for node_id, node in self.nodes_data.items():
            if not self.show_all_nodes and 'isFavorite' not in node.keys():
                continue
            
            if 'deviceMetrics' not in node.keys():
                continue
            
            with self.nodes_container:
                self._create_node_card(node_id, node)
    
    def _create_node_card(self, node_id: str, node: Dict[str, Any]) -> None:
        """Create a card for displaying node information."""
        with ui.card().classes('w-full mb-2'):
            with ui.row().classes('w-full items-center justify-between'):
                with ui.column().classes('flex-1'):
                    ui.label(node['user']['longName']).classes('text-h6')
                    ui.label(f"ID: {node_id}").classes('text-caption text-gray-600')
                    ui.label(f"Model: {node['user']['hwModel']}").classes('text-caption')
                
                with ui.column().classes('text-right'):
                    if 'deviceMetrics' in node:
                        battery_info = self.mesh_interface.get_battery_levels(node)
                        uptime_info = self.mesh_interface.get_uptime_string(node)
                        ui.label(battery_info).classes('text-sm')
                        ui.label(uptime_info).classes('text-sm text-gray-600')
    
    def _clear_nodes_display(self) -> None:
        """Clear the nodes display."""
        self.nodes_container.clear()
        with self.nodes_container:
            ui.label('Not connected').classes('text-gray-500')
    
    def run(self, **kwargs) -> None:
        """Run the GUI application."""
        self.setup_ui()
        ui.run(**kwargs)
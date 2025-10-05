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
        self.set_theme()
        self.connection_manager = MeshConnectionManager()
        self.mesh_interface: Optional[MeshInterface] = None
        self.connected = False
        self.show_all_nodes = True
        self.nodes_data: Dict[str, Any] = {}
        
        # UI components (initialized in setup_ui)
        self.tcp_host = None
        self.tcp_port = None
        self.serial_port = None
        self.connection_status = None
        self.show_all_toggle = None
        self.nodes_container = None
        self.refresh_nodes_button = None
    # To change the theme of NiceGUI, you can use the `ui.colors` object to set primary, secondary, and other color values.
    # You can also use `ui.dark_mode()` to enable dark mode.
    # Example: Set a custom theme (call this in __init__ or setup_ui as needed)
    def set_theme(self):
        """Set NiceGUI theme colors and mode."""
        # Example: set primary and secondary colors
        ui.colors(primary='#19d275', secondary='#7519d2', accent='#d27519', positive='#21BA45', negative='#C10015')
        # Enable dark mode (optional)
        # ui.dark_mode()  # Uncomment to enable dark mode

    def setup_ui(self) -> None:
        """Setup the main UI components."""
        ui.page_title("MeshViewer - Meshtastic Network Monitor")
        
        with ui.header().classes('items-center justify-between'):
            ui.label('MeshViewer').classes('text-h4')
            ui.label('Meshtastic Network Monitor').classes('text-subtitle2')
        
        with ui.row().classes('w-full'):
            with ui.column().classes('w-2/3'):
                self._setup_nodes_panel()

            with ui.column().classes('w-1/4'):
                self._setup_connection_panel()
            

    
    def _setup_connection_panel(self) -> None:
        """Setup the connection control panel."""
        with ui.card().classes('w-full'):
            ui.label('Connection').classes('text-h6')
            
            with ui.row().classes('w-full'):
                self.tcp_host = ui.input('TCP Host', value='192.168.0.114').classes('flex-1')
                self.tcp_port = ui.number('Port', value=4403).classes('w-20')
                ui.button('Connect TCP', on_click=self.connect_tcp).classes('w-1/4')

            
            with ui.row().classes('w-full'):
                self.serial_port = ui.input('Serial Port (optional)').classes('flex-1')
                ui.button('Connect Serial', on_click=self.connect_serial).classes('w-1/4')

            with ui.row().classes('w-full gap-2'):
                ui.button('Disconnect', on_click=self.disconnect).classes('flex-1').bind_visibility_from(self, 'connected')
            
            self.connection_status = ui.label('Disconnected').classes('text-caption')
    
    def _setup_nodes_panel(self) -> None:
        """Setup the nodes display panel."""
        with ui.card().classes('w-full'):
            with ui.row().classes('w-full items-center justify-between'):
                self.nodes_title = ui.label('Favourite Nodes' if not self.show_all_nodes else 'All Mesh Nodes').classes('text-h6')
                self.nodes_title.bind_text_from(self, 'show_all_nodes', lambda v: 'All Mesh Nodes' if v else 'Favourite Nodes')
                self.show_all_toggle = ui.checkbox('Show all Nodes', value=False).bind_value(self, 'show_all_nodes').on('update:model-value', lambda e: self.refresh_nodes())
            
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

    def hex_to_rgb(self, hex_str: str) -> tuple:
        """Convert hex color string to RGB tuple."""
        hex_str = hex_str.lstrip('#')
        if len(hex_str) == 3:
            hex_str = ''.join([c*2 for c in hex_str])
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

    def is_dark_color(self, rgb: tuple) -> bool:
        """Determine if an RGB color is dark based on luminance."""
        r, g, b = rgb
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        return luminance < 128

    def get_nodechip_colour(self, node_id):
        """
        Given a node_id, returns a tuple (bg_color, font_color) for the nodechip.
        bg_color is a hex string, font_color is either 'white' or 'black' depending on contrast.
        """
        short_id = node_id[-6:]
        bg_color = f'#{short_id}'
        try:
            rgb = self.hex_to_rgb(bg_color)
            font_color = 'white' if self.is_dark_color(rgb) else 'black'
        except Exception:
            # fallback in case of invalid hex
            bg_color = '#888888'
            font_color = 'white'
        return bg_color, font_color

    def _create_node_card(self, node_id: str, node: Dict[str, Any]) -> None:
        """Create a card for displaying node information."""
        with ui.card().classes('w-full mb-2'):
            bg_color, font_color = self.get_nodechip_colour(node_id)
            label_classes = 'text-h6 text-white' if font_color == 'white' else 'text-h6'

            # The "summary" (simplified view) goes in the expansion's "title" slot.
            # NiceGUI's ui.expansion uses the first argument as the header/summary.
            # We'll build a row for the summary, showing shortName, longName, HW, and User ID.

            # Avoid passing a function as the expansion header, since NiceGUI tries to serialize it and this causes
            # "Type is not JSON serializable: function" errors. Instead, build the summary content inline.

            with ui.expansion(value=False).classes('w-full') as exp:
                with exp.add_slot('header'):
                    # Visible all the time
                    with ui.row().classes('w-full items-center justify-between'):
                        with ui.row().classes('items-left'):
                            with ui.element('div').style(f'background-color: {bg_color};').classes('inline-block px-2 py-1 rounded mr-2'):
                                ui.label(node['user']['shortName']).classes(label_classes)
                            ui.label(node['user']['longName']).classes('text-h6')
                        with ui.row().classes('items-right'):
                            if 'deviceMetrics' in node:
                                battery_info = self.mesh_interface.get_battery_levels(node)
                                last_heard_info = self.mesh_interface.get_last_heard_string(node)
                                ui.label(battery_info).classes('text-sm')
                                ui.label(last_heard_info).classes('text-sm text-gray-600')

                # The expansion content is the detailed view
                with ui.row().classes('w-full items-center justify-between'):
                    if 'deviceMetrics' in node:
                        uptime_info = self.mesh_interface.get_uptime_string(node)
                        ui.label(uptime_info).classes('text-sm text-gray-600')
                        channel_util = node['deviceMetrics']['channelUtilization'] * 100
                        ui.label(f"Channel Util: {channel_util:.1f}%").classes('text-caption text-gray-600')
                    ui.label(f"HW: {node['user']['hwModel']}").classes('text-caption text-gray-600')
                    ui.label(f"User ID: {node_id}").classes('text-caption text-gray-600')


    def _clear_nodes_display(self) -> None:
        """Clear the nodes display."""
        self.nodes_container.clear()
        with self.nodes_container:
            ui.label('Not connected').classes('text-gray-500')
    
    def run(self, **kwargs) -> None:
        """Run the GUI application."""
        self.setup_ui()
        ui.run(**kwargs)
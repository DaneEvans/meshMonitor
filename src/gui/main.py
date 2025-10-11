"""
Main GUI module for MeshViewer using NiceGUI.
"""
from nicegui import ui
from typing import Optional, Dict, Any
from meshviewer.connection import MeshConnectionManager
from meshviewer.interface import MeshInterface
from meshviewer.config import ConfigManager
import time


class MeshViewerGUI:
    """Main GUI class for the MeshViewer application."""
    # active_threshold is now set from config in __init__
    dark = ui.dark_mode()

    def __init__(self, config_path: Optional[str] = None):
        """Initialize the GUI."""
        self.config = ConfigManager(config_path)

        self.set_theme()

        self.connection_manager = MeshConnectionManager()
        self.mesh_interface: Optional[MeshInterface] = None
        self.connected = False
        self.show_all_nodes = True
        self.nodes_data: Dict[str, Any] = {}
        
        # Get active threshold from config
        node_settings = self.config.get_node_settings()
        self.active_threshold = node_settings.get('active_threshold_hours', 3)
        
        # UI components (initialized in setup_ui)
        self.tcp_host = None
        self.tcp_port = None
        self.serial_port = None
        self.connection_status = None
        self.show_all_toggle = None
        self.nodes_container = None
        self.refresh_nodes_button = None
        self.auto_refresh_timer = None

    def set_theme(self):
        """Set NiceGUI theme colors and mode using native theming."""
        colors = self.config.get_theme_colors()
        
        # Set NiceGUI colors (this handles all the theming automatically)
        ui.colors(
            primary=colors.get('primary', '#2c2d3c'),
            secondary=colors.get('secondary', '#234d20'),
            accent=colors.get('accent', '#c9df8a'),
            positive=colors.get('positive', '#21BA45'),
            negative=colors.get('negative', '#C10015')
        )

    def setup_ui(self) -> None:
        """Setup the main UI components."""
        ui.page_title(self.config.get('app.page_title', 'MeshViewer - Meshtastic Network Monitor'))
        
        with ui.row().classes('w-full items-center justify-between p-4 bg-primary text-white'):
            logo_path = self.config.get('app.logo_path')
            ui.image(logo_path).style('max-width: 10vw; height: auto;')
            ui.label(self.config.get('app.title', 'MeshViewer')).classes('text-h4')
            ui.label(self.config.get('app.subtitle', 'Meshtastic Network Monitor')).classes('text-subtitle2')
        
        self.dark.enable()
        ui.switch('Dark mode').bind_value(self.dark).on('update:model-value', lambda _: self.refresh_nodes())

        # Responsive layout: on small screens, connection panel on top; on large screens, nodes panel on left
        with ui.row().classes('w-full flex-col md:flex-row gap-4'):
            with ui.column().classes('w-full md:w-2/3 order-2 md:order-1'):
                self._setup_nodes_panel()
            with ui.column().classes('w-full md:w-1/4 order-1 md:order-2'):
                self._setup_connection_panel()
        # Increase minimum width for the dark mode switch by 30%
        ui.query('label:has(input[type="checkbox"])').style('min-width: 130%')
            

    
    def _setup_connection_panel(self) -> None:
        """Setup the connection control panel."""
        ui_text = self.config.get_ui_text().get('connection', {})
        connection_defaults = self.config.get_connection_defaults()
        
        with ui.card().classes('w-full'):
            ui.label(ui_text.get('title', 'Connection')).classes('text-h6')
            
            with ui.row().classes('w-full max-w-full items-center gap-2 flex-nowrap'):
                self.tcp_host = ui.input('TCP Host', value=connection_defaults.get('default_tcp_host', '192.168.0.114')).classes('flex-1 min-w-0')
                self.tcp_port = ui.number(
                    'Port',
                    value=connection_defaults.get('default_tcp_port', 4403),
                    min=0,
                    max=9999,
                    step=1
                ).classes('w-1/6 min-w-0').props('maxlength=4')
                self.connect_tcp_button = ui.button('Connect TCP', on_click=self.connect_tcp).classes('w-1/4')
                def try_connect_once():
                    if not getattr(self, 'connected', False):
                        self.connect_tcp()
                ui.timer(0.5, try_connect_once, once=True)

            
            with ui.row().classes('w-full'):
                self.serial_port = ui.input('Serial Port (optional)').classes('flex-1')
                ui.button('Connect Serial', on_click=self.connect_serial).classes('w-1/4')

            with ui.row().classes('w-full gap-2'):
                ui.button('Disconnect', on_click=self.disconnect).classes('flex-1').bind_visibility_from(self, 'connected')
            
            self.connection_status = ui.label(ui_text.get('disconnected_status', 'Disconnected')).classes('text-caption')
    
    def _setup_nodes_panel(self) -> None:
        """Setup the nodes display panel."""
        ui_text = self.config.get_ui_text().get('nodes', {})
        
        with ui.card().classes('w-full'):
            # Node count display at the top
            def get_node_count_info(_=None):
                if not self.connected or not self.mesh_interface or not hasattr(self.mesh_interface, 'interface'):
                    return "Total Nodes: 0 | Active (3h): 0"
                
                nodes = list(self.mesh_interface.interface.nodes.values())
                total_nodes = len(nodes)
                
                # Count nodes heard from in the last 3 hours
                import time
                current_time = int(time.time())
                three_hours_ago = current_time - (self.active_threshold * 3600)
                active_nodes = 0
                
                for node in nodes:
                    if 'lastHeard' in node and node['lastHeard'] >= three_hours_ago:
                        active_nodes += 1
                
                return f"Nodes online: {active_nodes}/{total_nodes}"

            self.node_count_label = ui.label(get_node_count_info()).classes('text-h6 text-center w-full mb-2')
            self.node_count_label.bind_text_from(self, 'connected', get_node_count_info)
            self.node_count_label.bind_text_from(self, 'mesh_interface', get_node_count_info)
            
            with ui.row().classes('w-full items-center justify-between'):
                self.nodes_title = ui.label(ui_text.get('title_favorites', 'Favourite Nodes')).classes('text-h6')
                self.nodes_title.bind_text_from(self, 'show_all_nodes', lambda v: ui_text.get('title_all', 'All Mesh Nodes') if v else ui_text.get('title_favorites', 'Favourite Nodes'))
                self.show_all_toggle = ui.checkbox('Show all Nodes', value=False).bind_value(self, 'show_all_nodes').on('update:model-value', lambda e: self.refresh_nodes())
            
            self.nodes_container = ui.column().classes('w-full')
            self.refresh_nodes_button = ui.button('Refresh', on_click=self.refresh_nodes).bind_visibility_from(self, 'connected')
    
    def connect_tcp(self) -> None:
        """Connect via TCP."""
        host = self.tcp_host.value
        port = int(self.tcp_port.value)
        ui_text = self.config.get_ui_text().get('connection', {})
        
        if self.connection_manager.connect_tcp(host, port):
            self.mesh_interface = MeshInterface(self.connection_manager.get_interface())
            self.connected = True
            self.connection_status.text = ui_text.get('connected_tcp_status', 'Connected via TCP to {host}:{port}').format(host=host, port=port)
            self.connection_status.classes('text-green')
            # Set up comprehensive hooks to catch all packet types
            self.connection_manager.enable_auto_refresh()
            self.connection_manager.setup_comprehensive_hooks()
            self.refresh_nodes()
            # Start automatic refresh every 5 minutes
            self.start_auto_refresh()
        else:
            self.connection_status.text = ui_text.get('connection_failed_tcp', 'TCP connection failed')
            self.connection_status.classes('text-red')
    
    def connect_serial(self) -> None:
        """Connect via Serial."""
        port = self.serial_port.value if self.serial_port.value else None
        ui_text = self.config.get_ui_text().get('connection', {})
        
        if self.connection_manager.connect_serial(port):
            self.mesh_interface = MeshInterface(self.connection_manager.get_interface())
            self.connected = True
            port_display = port or 'auto-detected'
            self.connection_status.text = ui_text.get('connected_serial_status', 'Connected via Serial on {port}').format(port=port_display)
            self.connection_status.classes('text-green')
            # Set up comprehensive hooks to catch all packet types
            self.connection_manager.enable_auto_refresh()
            self.connection_manager.setup_comprehensive_hooks()
            self.refresh_nodes()
            # Start automatic refresh every 5 minutes
            self.start_auto_refresh()
        else:
            self.connection_status.text = ui_text.get('connection_failed_serial', 'Serial connection failed')
            self.connection_status.classes('text-red')
    
    def disconnect(self) -> None:
        """Disconnect from the network."""
        # Stop automatic refresh
        self.stop_auto_refresh()
        self.connection_manager.disconnect()
        self.mesh_interface = None
        self.connected = False
        ui_text = self.config.get_ui_text().get('connection', {})
        self.connection_status.text = ui_text.get('disconnected_status', 'Disconnected')
        self.connection_status.classes('text-gray')
        self._clear_nodes_display()
    
    def refresh_nodes(self) -> None:
        """Refresh the nodes display."""
        if not self.connected or not self.mesh_interface:
            return
        
        # Refresh nodes data and force last heard updates
        self.mesh_interface.refresh_nodes_data()
        self.mesh_interface.detect_last_heard_changes()
        self.mesh_interface.force_last_heard_update()
        
        self.nodes_data = self.mesh_interface.get_all_nodes_data()
        self._update_nodes_display()
        # Update the node count display
        if hasattr(self, 'node_count_label'):
            self.node_count_label.update()
    
    def _update_nodes_display(self) -> None:
        """Update the nodes display with current data."""
        self.nodes_container.clear()
        ui_text = self.config.get_ui_text().get('nodes', {})
        
        if not self.nodes_data:
            with self.nodes_container:
                ui.label(ui_text.get('no_nodes_found', 'No nodes found')).classes('text-gray-500')
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
        ui_text = self.config.get_ui_text().get('nodes', {})
        
        with ui.card().classes('w-full mb-1 py-1'):
            bg_color, font_color = self.get_nodechip_colour(node_id)
            label_classes = 'text-h6 text-white' if font_color == 'white' else 'text-h6'

            with ui.expansion(value=False).classes('w-full') as exp:
                with exp.add_slot('header'):  # Visible all the time
                    with ui.row().classes('w-full items-center justify-between'):
                        with ui.row().classes('items-left'):
                            with ui.element('div').style(f'background-color: {bg_color};').classes('inline-block px-2 py-1 rounded mr-2'):
                                ui.label(node['user']['shortName']).classes(label_classes).style(f'color: {font_color};')
                            ui.label(node['user']['longName']).classes('text-h6')
                        with ui.row().classes('items-right'):
                            if 'deviceMetrics' in node:
                                self.render_last_heard(node)
                                self.render_battery_string(node)


                # The expansion content is the detailed view
                with ui.row().classes('w-full items-center justify-between'):
                    if 'deviceMetrics' in node:
                        uptime_hours = self.mesh_interface.get_uptime(node, asString = False)
                        ui.label(f"up {uptime_hours:4.1f} hrs").classes('text-sm')
                        channel_util = node['deviceMetrics']['channelUtilization']
                        ui.label(f"{ui_text.get('channel_util_label', 'Channel Util')}: {channel_util:.1f}%").classes('text-caption')
                    ui.label(f"{ui_text.get('hw_label', 'HW')}: {node['user']['hwModel']}").classes('text-caption')
                    ui.label(f"{ui_text.get('user_id_label', 'User ID')}: {node_id}").classes('text-caption')


    def _clear_nodes_display(self) -> None:
        """Clear the nodes display."""
        self.nodes_container.clear()
        ui_text = self.config.get_ui_text().get('nodes', {})
        with self.nodes_container:
            ui.label(ui_text.get('not_connected', 'Not connected')).classes('text-gray-500')
        # Reset node count display
        if hasattr(self, 'node_count_label'):
            self.node_count_label.update()

    def render_battery_string(self, node):
        battery_level, voltage, is_charging = self.mesh_interface.get_node_battery_status(node, asString = False)
        if is_charging:
            bat_str = " Chg"
        else:
            bat_str = f"{battery_level:3}%"
        bat_str += f", {voltage:.3f}V "
        
        if self.dark.value:
            # When dark mode is on
            if is_charging:
                bat_color = "#82d0fa"
            elif battery_level < 60:
                bat_color = "#C10015"  # red for low battery
            else:
                bat_color = "#21ba45"

            voltage_color = "#bbbbbb"

        else:
            # Light mode
            if is_charging:
                bat_color = "#1565c0"  # deeper blue, higher saturation
            elif battery_level < 60:
                bat_color = "#C10015"  # red
            else:
                bat_color = "#1b8d2b"  # more saturated green for better contrast

            voltage_color = "#666666"


        return ui.html(
            f'<span class="text-sm">'
            f'<span style="color: {bat_color}; font-weight: bold;">{bat_str[:4]}</span>'
            f'<span style="color: {voltage_color};">{bat_str[4:]}</span>'
            f'</span>'
        )

    def render_last_heard(self, node):
        last_heard = self.mesh_interface.get_last_heard(node, asString = False);
        now = int(time.time())
        delta = now - last_heard
        if delta > 6 * 3600:
            last_heard_str = time.strftime("%H:%M %d/%m/%Y", time.localtime(last_heard))
        else:
            last_heard_str = time.strftime("%H:%M", time.localtime(last_heard))
        # Use HTML for last heard display with color based on time delta: >1h (yellow), >3h (orange), >6h (red)
        if delta > 6 * 3600:
            color = "#c0392b"  # red
        elif delta > 3 * 3600:
            color = "#e67e22"  # orange
        elif delta > 1 * 3600:
            color = "#ffe04b"  # yellow
        else:
            color = "#bbbbbb" if self.dark.value else "#444444"
        ui.html(
            f'<span class="text-sm" style="color:{color};">Last Heard:<br>{last_heard_str}</span>'
        )

    
    def start_auto_refresh(self) -> None:
        """Start automatic refresh every 5 minutes."""
        if self.auto_refresh_timer is None:
            self.auto_refresh_timer = ui.timer(300.0, self.refresh_nodes)  # 300 seconds = 5 minutes
            print("Auto-refresh started: refreshing every 5 minutes")
    
    def stop_auto_refresh(self) -> None:
        """Stop automatic refresh."""
        if self.auto_refresh_timer is not None:
            self.auto_refresh_timer.deactivate()
            self.auto_refresh_timer = None
            print("Auto-refresh stopped")
    
    def run(self, **kwargs) -> None:
        """Run the GUI application."""
        self.setup_ui()
        ui.run(**kwargs)
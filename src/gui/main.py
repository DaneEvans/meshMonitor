"""
Main GUI module for MeshViewer using NiceGUI.
"""
from nicegui import ui
from typing import Optional, Dict, Any
from meshviewer.connection import MeshConnectionManager, MqttConnectionManager
from meshviewer.interface import MeshInterface
from meshviewer.config import ConfigManager
from meshviewer.data_persistence import DataPersistence
import json
import math
import time
import plotly.graph_objects as go
import socket


class MeshViewerGUI:
    """Main GUI class for the MeshViewer application."""
    # active_threshold is now set from config in __init__
    dark = ui.dark_mode()

    def __init__(self, config_path: Optional[str] = None):
        """Initialize the GUI."""
        self.config = ConfigManager(config_path)

        self.set_theme()

        # Pass shared ConfigManager to connection manager so both use the same config
        self.connection_manager = MeshConnectionManager(cfg=self.config)
        self.mesh_interface: Optional[MeshInterface] = None
        self.connected = False
        self.show_all_nodes = True
        self.show_mqtt_nodes = True
        self.nodes_data: Dict[str, Any] = {}
        
        # Initialize data persistence
        self.data_persistence = DataPersistence()
        
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
        self.tabs = None
        self.battery_chart = None

        # MQTT
        self.mqtt_manager = MqttConnectionManager()
        self.mqtt_manager.set_on_update(self._on_mqtt_update)
        self.mqtt_connected = False
        self.mqtt_nodes_data: Dict[str, Any] = {}
        self.mqtt_status = None  # label set in setup_ui
        self.mqtt_host_input = None
        self.mqtt_user_input = None
        self.mqtt_pass_input = None
        self.mqtt_topic_input = None
        self.mqtt_reporters_container = None
        self.neighbour_packets = []
        self.neighbour_log_container = None
        self.neighbour_map_container = None
        self.neighbour_unknown_container = None
        self.reporter_aliases: Dict[str, str] = self.data_persistence.get_reporter_aliases()
        self.reporter_visibility: Dict[str, bool] = self.data_persistence.get_reporter_visibility()
        self._known_reporting_nodes: list[str] = []
        self._known_reporting_prefixes: Dict[str, str] = {}

        # Pre-populate with last-known node state so the display isn't empty on restart
        persisted = self.data_persistence.get_last_known_nodes()
        if persisted:
            self.mqtt_nodes_data = persisted
            # Seed the MQTT manager's internal cache so live updates merge into persisted data
            # rather than replacing it wholesale on the first packet
            with self.mqtt_manager._lock:
                for nid, node in persisted.items():
                    if nid not in self.mqtt_manager._nodes:
                        self.mqtt_manager._nodes[nid] = dict(node)

        persisted_neighbours = self.data_persistence.get_neighbour_packets()
        if persisted_neighbours:
            self.neighbour_packets = persisted_neighbours
            self.mqtt_manager.set_neighbor_packets(persisted_neighbours)
            print(f"DEBUG: Loaded {len(persisted_neighbours)} persisted neighbour packets into mqtt_manager")

        # Mark that persisted data has been loaded; will trigger display in setup_ui
        self.persisted_data_loaded = True

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
        ui.page_title(self.config.get('app.page_title', 'Mesh Monitor - Meshtastic Network Monitor'))
        
        with ui.row().classes('w-full items-center justify-between p-4 bg-primary text-white'):
            logo_path = self.config.get('app.logo_path')
            ui.image(logo_path).style('max-width: 10vw; height: auto;')
            with ui.column().classes('items-center'):
                ui.label(self.config.get('app.title', 'Mesh Monitor')).classes('text-h4')
                ui.label(self.config.get('app.subtitle', 'Meshtastic Network Monitor')).classes('text-subtitle2')
            with ui.column().classes('items-right'):
                ui.label(self.config.get('app.contactname', 'Dane Evans')).classes('text-subtitle2')
                ui.label(self.config.get('app.contactsite', 'https://meshtastic.org/')).classes('text-subtitle3')
        
        def get_local_ip():
            try:
                # Use UDP to avoid actual connection
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.connect(("8.8.8.8", 80))
                ip = sock.getsockname()[0]
                sock.close()
                return ip
            except Exception:
                return "127.0.0.1"

        self.dark.enable()
        with ui.row().classes('w-full items-center justify-between gap-4'):
            ui.switch('Dark mode').bind_value(self.dark).on('update:model-value', lambda _: self.refresh_nodes())
            ui.label(f"Server IP: {get_local_ip()}").classes('text-subtitle2 text-right')

        # Create tabs for different views
        with ui.tabs().classes('w-full') as self.tabs:
            ui.tab('Network View', icon='network_check')
            ui.tab('Battery History', icon='battery_charging_full')
            ui.tab('Neighbour map', icon='share')
            autoresp_text = self.config.get_ui_text().get('autoresponse', {})
            autoresp_tab = autoresp_text.get('tab_title', 'Auto Response')
            self._autoresp_tab = ui.tab(autoresp_tab, icon='smart_toy')
            automsg_text = self.config.get_ui_text().get('automessage', {})
            automsg_tab = automsg_text.get('tab_title', 'Auto Message')
            self._automsg_tab = ui.tab(automsg_tab, icon='schedule')

        def _update_mesh_tab_state(_=None):
            """Disable Auto Response/Message tabs when only connected via MQTT."""
            mesh_only = self.connected  # True = Meshtastic connected
            # disable = mqtt only (no meshtastic connection)
            disable = (not self.connected) and self.mqtt_connected
            for tab in (self._autoresp_tab, self._automsg_tab):
                if disable:
                    tab.props('disable')
                    tab.tooltip('Not available for MQTT-only connections')
                else:
                    tab.props(remove='disable')

        ui.timer(1.0, _update_mesh_tab_state)
        
        with ui.tab_panels(self.tabs, value='Network View').classes('w-full'):
            with ui.tab_panel('Network View'):
                # Responsive layout: on small screens, connection panel on top; on large screens, nodes panel on left
                with ui.row().classes('w-full flex-col md:flex-row gap-4'):
                    with ui.column().classes('w-full md:w-2/3 order-2 md:order-1'):
                        self._setup_nodes_panel()
                    with ui.column().classes('w-full md:w-1/4 order-1 md:order-2'):
                        self._setup_connection_panel()
                # Increase minimum width for the dark mode switch by 30%
                ui.query('label:has(input[type="checkbox"])').style('min-width: 130%')
            
            with ui.tab_panel('Battery History'):
                self._setup_battery_history_panel()

            with ui.tab_panel('Neighbour map'):
                self._setup_neighbour_map_panel()
            
            with ui.tab_panel(autoresp_tab):
                self._setup_autoresponse_panel()

            with ui.tab_panel(automsg_tab):
                self._setup_automessage_panel()

        # Defer display of persisted data until after event loop is initialized
        if getattr(self, 'persisted_data_loaded', False):
            def _trigger_initial_display():
                if self.mqtt_nodes_data:
                    self._update_nodes_display()
                # Neighbour views will be displayed via _setup_neighbour_map_panel which calls _update_neighbour_views()
            ui.timer(0.1, _trigger_initial_display, once=True)

    
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

        # ── MQTT connection card ────────────────────────────────────────
        with ui.card().classes('w-full mt-2'):
            ui.label('MQTT Connection').classes('text-h6')
            with ui.row().classes('w-full items-center gap-2 flex-nowrap'):
                self.mqtt_host_input = ui.input(
                    'Broker URL',
                    value=self.config.get('mqtt.default_host', ''),
                    placeholder='hostname or mqtt://host:1883',
                ).classes('flex-1 min-w-0')
            with ui.row().classes('w-full items-center gap-2'):
                self.mqtt_user_input = ui.input(
                    'Username',
                    value=self.config.get('mqtt.default_username', ''),
                ).classes('flex-1')
                self.mqtt_pass_input = ui.input(
                    'Password',
                    value=self.config.get('mqtt.default_password', ''),
                    password=True,
                    password_toggle_button=True,
                ).classes('flex-1')
            with ui.row().classes('w-full items-center gap-2'):
                self.mqtt_topic_input = ui.input(
                    'Topic',
                    value=self.config.get('mqtt.default_topic', '#'),
                    placeholder='# (all topics)',
                ).classes('flex-1')
            with ui.row().classes('w-full gap-2'):
                ui.button('Connect MQTT', on_click=self.connect_mqtt).classes('flex-1').bind_visibility_from(self, 'mqtt_connected', lambda v: not v)
                ui.button('Disconnect MQTT', on_click=self.disconnect_mqtt).classes('flex-1').bind_visibility_from(self, 'mqtt_connected')
            self.mqtt_status = ui.label('MQTT: Disconnected').classes('text-caption')

            with ui.separator().classes('my-2'):
                pass
            ui.label('Reporting node nicknames').classes('text-subtitle2')
            ui.label('Used in compact topic display: reported by <nickname>: prefix-channel').classes('text-caption text-gray-500')
            self.mqtt_reporters_container = ui.column().classes('w-full gap-1')
            self._refresh_mqtt_reporters_ui()

            def try_mqtt_autoconnect():
                if not self.mqtt_connected and self.config.get('mqtt.default_host', '').strip():
                    self.connect_mqtt()
            ui.timer(0.5, try_mqtt_autoconnect, once=True)
    
    def _setup_nodes_panel(self) -> None:
        """Setup the nodes display panel."""
        ui_text = self.config.get_ui_text().get('nodes', {})
        
        with ui.card().classes('w-full'):
            # Node count display at the top
            def get_node_count_info(_=None):
                if not self.connected or not self.mesh_interface or not hasattr(self.mesh_interface, 'interface'):
                    return "Total Nodes: 0 | Active (3h): 0"

                # Debounce display until values are final (avoid showing intermediate counts as the mesh loads)
                nodes = list(self.mesh_interface.interface.nodes.values())
                total_nodes = len(nodes)

                # Don't show count unless mesh info is 'stable' (i.e. mesh is fully loaded and not in early phases)

                # "Sticky" previous values for display
                if not hasattr(self, '_last_node_count_info'):
                    self._last_node_count_info = None
                    self._stable_node_counts = (0, 0)
                    self._last_update_time = 0

                current_time = int(time.time())
                three_hours_ago = current_time - (self.active_threshold * 3600)
                active_nodes = sum(1 for node in nodes if 'lastHeard' in node and node['lastHeard'] >= three_hours_ago)

                # Only update if both counts appear final (i.e. not in the process of loading more nodes)
                # Simple debounce: only update if the value is different after a short interval
                node_tuple = (active_nodes, total_nodes)
                now = time.time()
                if node_tuple != self._stable_node_counts:
                    self._stable_node_counts = node_tuple
                    self._last_update_time = now
                    return ''  # Blank out label until stable, hide in-between values
                elif now - self._last_update_time < 1.0:
                    return ''  # Wait at least 1s at stable value before displaying
                else:
                    info_str = f"Nodes online: {active_nodes}/{total_nodes}"
                    self._last_node_count_info = info_str
                    return info_str

            self.node_count_label = ui.label(get_node_count_info()).classes('text-h6 text-center w-full mb-2')
            self.node_count_label.bind_text_from(self, 'connected', get_node_count_info)
            self.node_count_label.bind_text_from(self, 'mesh_interface', get_node_count_info)
            
            with ui.row().classes('w-full items-center justify-between'):
                self.nodes_title = ui.label(ui_text.get('title_favorites', 'Favourite Nodes')).classes('text-h6')
                self.nodes_title.bind_text_from(self, 'show_all_nodes', lambda v: ui_text.get('title_all', 'All Mesh Nodes') if v else ui_text.get('title_favorites', 'Favourite Nodes'))
                self.show_all_toggle = ui.checkbox('Show all Nodes', value=False).bind_value(self, 'show_all_nodes').on('update:model-value', lambda e: self.refresh_nodes())
                ui.checkbox('Include MQTT', value=True).bind_value(self, 'show_mqtt_nodes').on('update:model-value', lambda e: self.refresh_nodes())
            
            self.nodes_container = ui.column().classes('w-full')
            self.refresh_nodes_button = ui.button('Refresh', on_click=self.refresh_nodes).bind_visibility_from(self, 'connected')

    
    def _setup_battery_history_panel(self) -> None:
        """Setup the battery history panel."""
        with ui.card().classes('w-full'):
            ui.label('Battery History').classes('text-h6 mb-4')
            
            # Controls
            with ui.row().classes('w-full items-center gap-4 mb-4'):
                self.days_selector = ui.select(
                    options={
                        0.042: '1 Hour', 0.25: '6 Hours', 0.5: '12 Hours',
                        1: '1 Day', 3: '3 Days', 7: '7 Days', 14: '14 Days', 30: '30 Days'
                    },
                    value=7,
                    label='Time Period'
                ).classes('w-32').on('update:model-value', lambda e: self.update_battery_chart())
                
                self.node_selector = ui.select(
                    options={},
                    value=None,
                    label='Node'
                ).classes('flex-1').on('update:model-value', lambda e: self.update_battery_chart())
                
                ui.button('Refresh Chart', on_click=self.update_battery_chart).classes('w-32')
            
            # Chart container
            self.battery_chart_container = ui.column().classes('w-full')
            
            # Data summary
            self.data_summary_container = ui.column().classes('w-full mt-4')
            
            # Initial load
            self.update_battery_chart()

    def _setup_autoresponse_panel(self) -> None:
        """Setup the auto response (auto-react) settings panel.

        Notes:
        - These settings are runtime-only overrides (they are not written to config.yaml).
        - They apply immediately to the active `MeshConnectionManager`.
        """
        ui_text = self.config.get_ui_text().get('autoresponse', {})
        with ui.card().classes('w-full'):
            ui.label(ui_text.get('title', 'Auto Response')).classes('text-h6')
            ui.label(ui_text.get('subtitle', 'Session-only settings (won’t persist after reboot).')).classes('text-caption text-gray-500')

            with ui.row().classes('w-full flex-col md:flex-row gap-4 items-start md:items-center'):
                auto_enabled = ui.switch(ui_text.get('enable_label', 'Enable auto react'), value=self.connection_manager.enable_auto_react)

                emoji_options = {e: e for e in getattr(self.connection_manager, 'SUPPORTED_TAPBACK_EMOJIS', ["🤖", "✅", "👍"])}
                emoji_select = ui.select(
                    options=emoji_options,
                    value=self.connection_manager.tapback_emoji,
                    label=ui_text.get('emoji_label', 'Tapback emoji'),
                ).classes('w-40')

                status = ui.label().classes('text-caption')

            def _refresh_status() -> None:
                enabled = bool(self.connection_manager.enable_auto_react)
                emoji = self.connection_manager.tapback_emoji
                conn = ui_text.get('status_connected', 'connected') if self.connected else ui_text.get('status_not_connected', 'not connected')
                status_prefix = ui_text.get('status_prefix', 'Status')
                auto_key = ui_text.get('status_auto_react', 'auto react')
                emoji_key = ui_text.get('status_emoji', 'emoji')
                on_label = ui_text.get('status_on', 'ON')
                off_label = ui_text.get('status_off', 'OFF')
                status.text = f"{status_prefix}: {conn} | {auto_key}: {on_label if enabled else off_label} | {emoji_key}: {emoji}"
                status.update()

            def _apply_auto_enabled(e) -> None:
                # No blocking work here; just set runtime flags.
                self.connection_manager.set_auto_react_enabled(bool(getattr(e, "value", e)))
                _refresh_status()

            def _apply_emoji(e) -> None:
                self.connection_manager.set_tapback_emoji(str(getattr(e, "value", e)))
                # Ensure UI stays consistent with allowlist
                emoji_select.value = self.connection_manager.tapback_emoji
                _refresh_status()

            # Use NiceGUI's value-change hooks to ensure these always fire.
            auto_enabled.on_value_change(_apply_auto_enabled)
            emoji_select.on_value_change(_apply_emoji)

            # Keep the status fresh without user interaction (lightweight, non-blocking)
            ui.timer(1.0, _refresh_status)
            _refresh_status()

    def _setup_automessage_panel(self) -> None:
        """Setup the auto message (scheduled broadcast) settings panel.

        Notes:
        - These settings are runtime-only overrides (they are not written to config.yaml).
        - Messages are sent by `MeshConnectionManager` while connected.
        """
        ui_text = self.config.get_ui_text().get('automessage', {})
        with ui.card().classes('w-full'):
            ui.label(ui_text.get('title', 'Auto Message')).classes('text-h6')
            ui.label(ui_text.get('subtitle', 'Session-only settings (won’t persist after reboot).')).classes('text-caption text-gray-500')

            # Draft list kept in the UI; manager filters/validates before scheduling.
            draft_messages = list(self.connection_manager.get_auto_messages())
            # Ensure each draft has an explicit enabled flag; existing config messages default to enabled.
            for m in draft_messages:
                if 'enabled' not in m:
                    m['enabled'] = True

            status = ui.label().classes('text-caption')
            messages_container = ui.column().classes('w-full')

            def _apply_to_manager() -> None:
                self.connection_manager.set_auto_messages(draft_messages)

            def _refresh_status() -> None:
                enabled = bool(getattr(self.connection_manager, 'enable_auto_message', False))
                conn = ui_text.get('status_connected', 'connected') if self.connected else ui_text.get('status_not_connected', 'not connected')
                status_prefix = ui_text.get('status_prefix', 'Status')
                auto_key = ui_text.get('status_auto_message', 'auto message')
                msgs_key = ui_text.get('status_messages', 'messages')
                on_label = ui_text.get('status_on', 'ON')
                off_label = ui_text.get('status_off', 'OFF')
                active_count = len(self.connection_manager.get_auto_messages())
                status.text = f"{status_prefix}: {conn} | {auto_key}: {on_label if enabled else off_label} | {msgs_key}: {active_count}"
                status.update()

            def _render_rows() -> None:
                messages_container.clear()

                if not draft_messages:
                    with messages_container:
                        ui.label('(no scheduled messages)').classes('text-gray-500 text-caption')
                    return

                interval_label = ui_text.get('interval_label', 'Interval (mins)')
                channel_label = ui_text.get('channel_label', 'Channel')
                message_label = ui_text.get('message_label', 'Message')
                delete_label = ui_text.get('delete_label', 'Delete')

                for i, m in enumerate(draft_messages):
                    with messages_container:
                        with ui.row().classes('w-full items-center gap-2 flex-col md:flex-row'):
                            row_enabled = ui.checkbox(
                                'Enabled',
                                value=bool(m.get('enabled', False)),
                            ).classes('w-24')
                            interval_in = ui.number(
                                interval_label,
                                value=m.get('interval', 15),
                                min=0.1,
                                step=1,
                            ).classes('w-40')
                            channel_in = ui.number(
                                channel_label,
                                value=m.get('channel', 0),
                                min=0,
                                step=1,
                            ).classes('w-28')
                            msg_in = ui.input(message_label, value=m.get('msg', '')).classes('flex-1 min-w-0')

                            def _delete(_=None, idx=i) -> None:
                                try:
                                    draft_messages.pop(idx)
                                except Exception:
                                    return
                                _apply_to_manager()
                                _render_rows()
                                _refresh_status()

                            ui.button(delete_label, on_click=_delete).props('color=negative').classes('w-28')

                            def _set_interval(e, idx=i) -> None:
                                try:
                                    draft_messages[idx]['interval'] = float(getattr(e, 'value', e))
                                except Exception:
                                    draft_messages[idx]['interval'] = getattr(e, 'value', e)
                                _apply_to_manager()
                                _refresh_status()

                            def _set_channel(e, idx=i) -> None:
                                try:
                                    draft_messages[idx]['channel'] = int(getattr(e, 'value', e))
                                except Exception:
                                    draft_messages[idx]['channel'] = getattr(e, 'value', e)
                                _apply_to_manager()
                                _refresh_status()

                            def _set_msg(e, idx=i) -> None:
                                draft_messages[idx]['msg'] = str(getattr(e, 'value', e))
                                _apply_to_manager()
                                _refresh_status()

                            def _set_row_enabled(e, idx=i) -> None:
                                draft_messages[idx]['enabled'] = bool(getattr(e, 'value', e))
                                _apply_to_manager()
                                _refresh_status()

                            row_enabled.on_value_change(_set_row_enabled)
                            interval_in.on_value_change(_set_interval)
                            channel_in.on_value_change(_set_channel)
                            msg_in.on_value_change(_set_msg)

            with ui.row().classes('w-full items-center gap-4'):
                enable_switch = ui.switch(
                    ui_text.get('enable_label', 'Enable auto messages'),
                    value=bool(getattr(self.connection_manager, 'enable_auto_message', False)),
                )

                def _apply_enabled(e) -> None:
                    self.connection_manager.set_auto_message_enabled(bool(getattr(e, "value", e)))
                    _refresh_status()

                enable_switch.on_value_change(_apply_enabled)

                def _add_message() -> None:
                    # New rows start disabled so you can finish typing before they are eligible to send.
                    draft_messages.append({'interval': 15, 'channel': 0, 'msg': '', 'enabled': False})
                    _apply_to_manager()
                    _render_rows()
                    _refresh_status()

                ui.button(ui_text.get('add_label', 'Add message'), on_click=_add_message).classes('w-40')

            ui.label('Channel index: 0 = Primary, 1 = Secondary, ...').classes('text-caption text-gray-500')

            _render_rows()
            ui.timer(1.0, _refresh_status)
            _refresh_status()

    def _setup_neighbour_map_panel(self) -> None:
        """Setup Neighbour map tab with packet log and neighbor map sections."""
        with ui.column().classes('w-full gap-4'):
            with ui.row().classes('w-full gap-4 flex-col lg:flex-row items-start'):
                with ui.card().classes('w-full lg:flex-1'):
                    ui.label('map').classes('text-h6')
                    ui.label('Latest reported neighbour links by node').classes('text-caption text-gray-500')
                    self.neighbour_map_container = ui.column().classes('w-full gap-1')

                with ui.card().classes('w-full lg:w-80'):
                    ui.label('visible, but neighbours not known').classes('text-h6')
                    ui.label('Last seen within 3 hours, and neither reports neighbours nor appears in any latest neighbour list').classes('text-caption text-gray-500')
                    self.neighbour_unknown_container = ui.column().classes('w-full gap-1')

            with ui.expansion('log', value=False).classes('w-full'):
                ui.label('Collected neighbourinfo MQTT packets').classes('text-caption text-gray-500')
                self.neighbour_log_container = ui.column().classes('w-full gap-1')

        self._update_neighbour_views()

    @staticmethod
    def _parse_mqtt_topic(topic: str) -> Dict[str, str]:
        """Parse MQTT topic into prefix/channel/reporter components when possible."""
        raw = str(topic or '').strip().strip('/')
        if not raw:
            return {'prefix': '', 'channel': '', 'reporter': ''}

        parts = [p for p in raw.split('/') if p]
        reporter = parts[-1] if parts else ''
        prefix = ''
        channel = ''

        # Pattern: <prefix>/<port>/json/<channel>/<reporter>
        # Example: msh/ANZ/flamingo/2/json/CRS_INFRA/!a0cb10f8
        for i in range(len(parts) - 3):
            if parts[i].isdigit() and parts[i + 1].lower() == 'json':
                prefix = '/'.join(parts[:i])
                channel = parts[i + 2]
                break

        # Best-effort fallback when pattern differs
        if not channel and len(parts) >= 2:
            channel = parts[-2]
        if not prefix and len(parts) >= 4:
            prefix = '/'.join(parts[:-4])

        return {'prefix': prefix, 'channel': channel, 'reporter': reporter}

    def _get_reporter_name(self, reporter_id: str) -> str:
        """Return reporter nickname when set, else raw reporter id."""
        key = str(reporter_id or '').strip()
        if not key:
            return ''
        alias = str(self.reporter_aliases.get(key, '') or '').strip()
        return alias if alias else key

    def _format_mqtt_topic_compact(self, topic: str) -> str:
        """Build compact MQTT path display: 🌉 nickname nodeID: prefix-channel."""
        parsed = self._parse_mqtt_topic(topic)
        reporter_id = parsed.get('reporter', '')
        alias = str(self.reporter_aliases.get(reporter_id, '') or '').strip()
        prefix = parsed.get('prefix', '')
        channel = parsed.get('channel', '')

        prefix_channel = ''
        if prefix and channel:
            prefix_channel = f'{prefix}-{channel}'
        elif prefix:
            prefix_channel = prefix
        elif channel:
            prefix_channel = channel
        else:
            parts = [p for p in str(topic or '').split('/') if p]
            prefix_channel = '/'.join(parts[-3:]) if parts else ''

        if alias and reporter_id:
            reporter_display = f'\U0001f309 {alias} {reporter_id}'
        elif reporter_id:
            reporter_display = f'\U0001f309 {reporter_id}'
        else:
            reporter_display = ''

        if reporter_display and prefix_channel:
            return f'{reporter_display}: {prefix_channel}'
        return reporter_display or prefix_channel

    def _collect_reporting_nodes(self) -> list[str]:
        """Collect all known MQTT reporting node ids from topic paths."""
        reporters = set()

        for node in self.mqtt_nodes_data.values():
            topic = str((node or {}).get('mqtt_topic') or '').strip()
            if not topic:
                continue
            reporter = self._parse_mqtt_topic(topic).get('reporter', '')
            if reporter:
                reporters.add(reporter)

        for pkt in self.neighbour_packets:
            topic = str((pkt or {}).get('_topic') or '').strip()
            if not topic:
                continue
            reporter = self._parse_mqtt_topic(topic).get('reporter', '')
            if reporter:
                reporters.add(reporter)

        return sorted(reporters)

    def _collect_reporting_prefixes(self) -> Dict[str, str]:
        """Collect latest known topic prefix label by reporting node id."""
        prefix_by_reporter: Dict[str, str] = {}

        def _prefix_label_from_topic(topic: str) -> str:
            parsed = self._parse_mqtt_topic(topic)
            prefix = str(parsed.get('prefix', '') or '').strip()
            channel = str(parsed.get('channel', '') or '').strip()
            if prefix:
                return prefix
            if channel:
                return channel
            parts = [p for p in str(topic or '').split('/') if p]
            return '/'.join(parts[-3:]) if parts else ''

        for node in self.mqtt_nodes_data.values():
            topic = str((node or {}).get('mqtt_topic') or '').strip()
            if not topic:
                continue
            reporter = self._parse_mqtt_topic(topic).get('reporter', '')
            if not reporter:
                continue
            label = _prefix_label_from_topic(topic)
            if label:
                prefix_by_reporter[reporter] = label

        for pkt in self.neighbour_packets:
            topic = str((pkt or {}).get('_topic') or '').strip()
            if not topic:
                continue
            reporter = self._parse_mqtt_topic(topic).get('reporter', '')
            if not reporter:
                continue
            label = _prefix_label_from_topic(topic)
            if label:
                prefix_by_reporter[reporter] = label

        return prefix_by_reporter

    def _set_reporter_alias(self, reporter_id: str, alias_value: Any) -> None:
        """Set/update nickname for a reporter node id and persist it."""
        key = str(reporter_id or '').strip()
        if not key:
            return
        alias = str(alias_value or '').strip()
        old_alias = self.reporter_aliases.get(key, '')
        if alias == old_alias:
            return  # No change; skip save and re-render
        if alias:
            self.reporter_aliases[key] = alias
        else:
            self.reporter_aliases.pop(key, None)
        self.data_persistence.save_reporter_aliases(self.reporter_aliases)
        # Do NOT rebuild reporters UI here — that would destroy the input the user is typing in
        self._update_nodes_display()

    def _is_reporter_visible(self, reporter_id: str) -> bool:
        """Return True when a reporter source is enabled for display."""
        key = str(reporter_id or '').strip()
        if not key:
            return True
        return bool(self.reporter_visibility.get(key, True))

    def _is_node_visible_for_reporter(self, node: Dict[str, Any]) -> bool:
        """Return True when a node's MQTT reporter source is enabled."""
        topic = str((node or {}).get('mqtt_topic') or '').strip()
        if not topic:
            return True
        reporter = self._parse_mqtt_topic(topic).get('reporter', '')
        return self._is_reporter_visible(reporter)

    def _set_reporter_visibility(self, reporter_id: str, visible: bool) -> None:
        """Set whether a reporter source should be shown in node/map views."""
        key = str(reporter_id or '').strip()
        if not key:
            return
        self.reporter_visibility[key] = bool(visible)
        self.data_persistence.save_reporter_visibility(self.reporter_visibility)
        self._refresh_mqtt_reporters_ui(force=True)
        self._update_nodes_display()
        self._update_neighbour_views()

    def _refresh_mqtt_reporters_ui(self, force: bool = False) -> None:
        """Refresh MQTT settings section listing reporting nodes and nickname inputs."""
        if self.mqtt_reporters_container is None:
            return

        reporters = self._collect_reporting_nodes()
        reporter_prefixes = self._collect_reporting_prefixes()
        if not force and reporters == self._known_reporting_nodes and reporter_prefixes == self._known_reporting_prefixes:
            return
        self._known_reporting_nodes = list(reporters)
        self._known_reporting_prefixes = dict(reporter_prefixes)

        self.mqtt_reporters_container.clear()
        with self.mqtt_reporters_container:
            if not reporters:
                ui.label('No reporting nodes discovered yet').classes('text-caption text-gray-500')
                return

            with ui.row().classes('w-full items-center gap-2 pb-1 border-b border-gray-300/40'):
                ui.label('ID').classes('text-caption font-semibold w-40')
                ui.label('Nickname').classes('text-caption font-semibold flex-1')
                ui.label('Show').classes('text-caption font-semibold w-16 text-right')

            for reporter in reporters:
                is_visible = self._is_reporter_visible(reporter)
                with ui.row().classes('w-full items-center gap-2'):
                    with ui.column().classes('w-40 gap-0'):
                        ui.label(reporter).classes('text-caption font-mono')
                        prefix_label = str(reporter_prefixes.get(reporter, '') or '').strip()
                        if prefix_label:
                            ui.label(prefix_label).classes('text-[11px] text-gray-500 -mt-1 break-all')
                    # on_change gives ValueChangeEventArguments with a reliable .value
                    ui.input(
                        '',
                        value=self.reporter_aliases.get(reporter, ''),
                        placeholder='optional nickname',
                        on_change=lambda e, rid=reporter: self._set_reporter_alias(rid, e.value)
                    ).classes('flex-1')
                    ui.switch(
                        '',
                        value=is_visible,
                        on_change=lambda e, rid=reporter: self._set_reporter_visibility(rid, bool(e.value))
                    ).props('dense').classes('w-16 justify-end')

    @staticmethod
    def _to_node_id(value: Any) -> str:
        """Convert numeric or string node identifier to canonical !xxxxxxxx form when possible."""
        if value is None:
            return ''
        if isinstance(value, str):
            s = value.strip().lower()
            if not s:
                return ''
            if s.startswith('!'):
                return s
            try:
                return f"!{int(s):08x}"
            except Exception:
                return s
        try:
            return f"!{int(value):08x}"
        except Exception:
            return str(value)

    @staticmethod
    def _format_time_ago(timestamp: int) -> str:
        """Return a compact relative time string for a unix timestamp."""
        if timestamp <= 0:
            return 'unknown'
        delta = max(0, int(time.time()) - int(timestamp))
        if delta < 60:
            return f'{delta}s ago'
        if delta < 3600:
            return f'{delta // 60}m ago'
        if delta < 86400:
            hours = delta // 3600
            minutes = (delta % 3600) // 60
            return f'{hours}h {minutes}m ago' if minutes else f'{hours}h ago'
        days = delta // 86400
        hours = (delta % 86400) // 3600
        return f'{days}d {hours}h ago' if hours else f'{days}d ago'

    def _update_neighbour_views(self) -> None:
        """Refresh Neighbour map tab sections from collected MQTT packets."""
        self.neighbour_packets = self.mqtt_manager.get_neighbor_packets()
        print(f"DEBUG: _update_neighbour_views retrieved {len(self.neighbour_packets)} packets from mqtt_manager")
        self._refresh_mqtt_reporters_ui()

        if self.neighbour_log_container is None or self.neighbour_map_container is None or self.neighbour_unknown_container is None:
            return

        # ---- log section ----
        self.neighbour_log_container.clear()
        with self.neighbour_log_container:
            total = len(self.neighbour_packets)
            ui.label(f'Packets collected: {total}').classes('text-caption text-gray-500')
            if total == 0:
                ui.label('No neighbour packets yet').classes('text-gray-500')
            else:
                # Keep UI manageable while still collecting all in memory
                recent_packets = self.neighbour_packets[-200:]
                if total > len(recent_packets):
                    ui.label(f'Showing latest {len(recent_packets)} packets').classes('text-caption text-gray-500')
                for pkt in reversed(recent_packets):
                    ts = pkt.get('timestamp', pkt.get('_received_at', ''))
                    node_from = self._to_node_id(pkt.get('from'))
                    topic = pkt.get('_topic', '')
                    with ui.column().classes('w-full rounded border border-gray-300 p-2 bg-gray-50 dark:bg-gray-900'):
                        ui.label(f'{ts}  {node_from}  {topic}').classes('text-caption font-mono')
                        ui.label(json.dumps(pkt, separators=(',', ':'), sort_keys=True)).classes('text-caption font-mono break-all')

        # ---- map section ----
        self.neighbour_map_container.clear()
        edges: Dict[tuple, Dict[str, Any]] = {}
        reporter_nodes = set()
        latest_packets_by_reporter: Dict[str, Dict[str, Any]] = {}
        for pkt in self.neighbour_packets:
            if (pkt.get('type') or '').lower() not in ('neighborinfo', 'neighbourinfo'):
                continue
            payload = pkt.get('payload') or {}
            reporter = self._to_node_id(payload.get('node_id') or pkt.get('from'))
            if not reporter:
                continue
            if not self._is_reporter_visible(reporter):
                continue
            reporter_nodes.add(reporter)
            ts = int(pkt.get('timestamp') or pkt.get('_received_at') or 0)
            current_latest = latest_packets_by_reporter.get(reporter)
            current_latest_ts = int((current_latest or {}).get('timestamp') or (current_latest or {}).get('_received_at') or 0)
            if current_latest is None or ts >= current_latest_ts:
                latest_packets_by_reporter[reporter] = pkt

        for reporter, pkt in latest_packets_by_reporter.items():
            payload = pkt.get('payload') or {}
            ts = int(pkt.get('timestamp') or pkt.get('_received_at') or 0)
            for n in payload.get('neighbors') or []:
                neighbour = self._to_node_id(n.get('node_id'))
                if not neighbour:
                    continue
                key = (reporter, neighbour)
                edges[key] = {
                    'count': 1,
                    'snr': n.get('snr'),
                    'last_ts': ts,
                }

        # ---- unknown neighbour section ----
        self.neighbour_unknown_container.clear()
        three_hours_ago = int(time.time()) - (3 * 3600)
        visible_nodes: Dict[str, Any] = dict(self.nodes_data)
        for node_id, node in self.mqtt_nodes_data.items():
            if node_id not in visible_nodes:
                if not self._is_node_visible_for_reporter(node):
                    continue
                visible_nodes[node_id] = node

        known_neighbour_nodes = set(edges_node for edge in edges for edges_node in edge) | set(latest_packets_by_reporter.keys())
        unknown_nodes = []
        for node_id, node in visible_nodes.items():
            last_heard = int((node or {}).get('lastHeard') or 0)
            if last_heard < three_hours_ago:
                continue
            if node_id in known_neighbour_nodes:
                continue
            user = node.get('user') or {}
            name = user.get('longName') or user.get('shortName') or node_id
            unknown_nodes.append((last_heard, node_id, name))

        unknown_nodes.sort(reverse=True)
        with self.neighbour_unknown_container:
            ui.label(f'Nodes: {len(unknown_nodes)}').classes('text-caption text-gray-500')
            if not unknown_nodes:
                ui.label('None').classes('text-gray-500')
            else:
                for last_heard, node_id, name in unknown_nodes:
                    ui.label(f'{name} ({node_id})').classes('text-caption')
                    ui.label(f'last heard: {self._format_time_ago(last_heard)}').classes('text-caption text-gray-500 -mt-2 mb-1')

        with self.neighbour_map_container:
            node_ids = sorted({node_id for edge in edges for node_id in edge} | set(latest_packets_by_reporter.keys()))
            ui.label(f'Links discovered: {len(edges)} | Nodes: {len(node_ids)}').classes('text-caption text-gray-500')
            if not edges:
                ui.label('No neighbour links yet').classes('text-gray-500')
            else:
                width = 960
                height = 720
                padding = 90

                # ── Fruchterman-Reingold force-directed layout ───────────────
                n = len(node_ids)
                node_index = {nid: i for i, nid in enumerate(node_ids)}
                adj_sets: list = [set() for _ in range(n)]
                for (rn, nn) in edges:
                    ri, ni = node_index.get(rn, -1), node_index.get(nn, -1)
                    if ri >= 0 and ni >= 0:
                        adj_sets[ri].add(ni)
                        adj_sets[ni].add(ri)

                # Deterministic circular seed
                cx0, cy0 = width / 2.0, height / 2.0
                r0 = min(width - 2 * padding, height - 2 * padding) * 0.38
                pos_x = [cx0 + r0 * math.cos((2 * math.pi * i / max(n, 1)) - math.pi / 2) for i in range(n)]
                pos_y = [cy0 + r0 * math.sin((2 * math.pi * i / max(n, 1)) - math.pi / 2) for i in range(n)]

                k_fd = math.sqrt((width - 2 * padding) * (height - 2 * padding) / max(n, 1))
                iters = 300
                for it in range(iters):
                    fx = [0.0] * n
                    fy = [0.0] * n
                    # Repulsion between every pair
                    for i in range(n):
                        for j in range(i + 1, n):
                            dx = pos_x[i] - pos_x[j]
                            dy = pos_y[i] - pos_y[j]
                            dist = max((dx * dx + dy * dy) ** 0.5, 1.0)
                            rep = k_fd * k_fd / dist
                            ux, uy = dx / dist, dy / dist
                            fx[i] += ux * rep;  fy[i] += uy * rep
                            fx[j] -= ux * rep;  fy[j] -= uy * rep
                    # Attraction along edges
                    for i in range(n):
                        for j in adj_sets[i]:
                            if j > i:
                                dx = pos_x[j] - pos_x[i]
                                dy = pos_y[j] - pos_y[i]
                                dist = max((dx * dx + dy * dy) ** 0.5, 1.0)
                                att = dist * dist / k_fd
                                ux, uy = dx / dist, dy / dist
                                fx[i] += ux * att;  fy[i] += uy * att
                                fx[j] -= ux * att;  fy[j] -= uy * att
                    # Apply displacement with cooling
                    temp = max(5.0, (width / 8.0) * (1.0 - it / iters))
                    for i in range(n):
                        mag = max((fx[i] * fx[i] + fy[i] * fy[i]) ** 0.5, 1e-9)
                        disp = min(mag, temp)
                        pos_x[i] = max(padding, min(width - padding, pos_x[i] + fx[i] / mag * disp))
                        pos_y[i] = max(padding, min(height - padding, pos_y[i] + fy[i] / mag * disp))

                node_positions: Dict[str, tuple] = {node_ids[i]: (pos_x[i], pos_y[i]) for i in range(n)}

                def _escape(text: str) -> str:
                    return (
                        str(text)
                        .replace('&', '&amp;')
                        .replace('<', '&lt;')
                        .replace('>', '&gt;')
                        .replace('"', '&quot;')
                    )

                svg_parts = [
                    f'<svg viewBox="0 0 {width} {height}" class="w-full" style="min-height: 720px; background: rgba(128,128,128,0.06); border-radius: 12px;">',
                    '<defs>',
                    '<marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">',
                    '<polygon points="0 0, 10 3.5, 0 7" fill="#64748b"></polygon>',
                    '</marker>',
                    '<marker id="arrowhead-rev" markerWidth="10" markerHeight="7" refX="1" refY="3.5" orient="auto">',
                    '<polygon points="10 0, 0 3.5, 10 7" fill="#64748b"></polygon>',
                    '</marker>',
                    '</defs>',
                ]

                # Build bidirectional edge pairs to avoid duplicate lines
                processed_edges = set()

                for (reporter, neighbour), edge in edges.items():
                    pair = tuple(sorted([reporter, neighbour]))
                    if pair in processed_edges:
                        continue
                    processed_edges.add(pair)

                    x1, y1 = node_positions[neighbour]
                    x2, y2 = node_positions[reporter]
                    dx = x2 - x1
                    dy = y2 - y1
                    length = max((dx * dx + dy * dy) ** 0.5, 1)
                    node_radius = 28
                    start_x = x1 + (dx / length) * node_radius
                    start_y = y1 + (dy / length) * node_radius
                    end_x = x2 - (dx / length) * node_radius
                    end_y = y2 - (dy / length) * node_radius

                    snr_forward = edge['snr']
                    snr_forward_txt = f'{snr_forward}dB' if snr_forward is not None else 'n/a'

                    # Check for reverse direction
                    reverse_key = (neighbour, reporter)
                    has_reverse = reverse_key in edges
                    snr_reverse = edges[reverse_key]['snr'] if has_reverse else None
                    snr_reverse_txt = f'{snr_reverse}dB' if snr_reverse is not None else 'n/a'

                    title_txt = _escape(f'{neighbour} → {reporter}: {snr_forward_txt}')
                    if has_reverse:
                        title_txt += _escape(f' | {reporter} → {neighbour}: {snr_reverse_txt}')

                    # Draw single line with appropriate arrowheads
                    if has_reverse:
                        # Bidirectional: both arrowheads
                        svg_parts.append(
                            f'<line x1="{start_x:.1f}" y1="{start_y:.1f}" x2="{end_x:.1f}" y2="{end_y:.1f}" stroke="#64748b" stroke-width="2" marker-start="url(#arrowhead-rev)" marker-end="url(#arrowhead)"><title>{title_txt}</title></line>'
                        )
                    else:
                        # Unidirectional: single arrowhead at the end
                        svg_parts.append(
                            f'<line x1="{start_x:.1f}" y1="{start_y:.1f}" x2="{end_x:.1f}" y2="{end_y:.1f}" stroke="#64748b" stroke-width="2" marker-end="url(#arrowhead)"><title>{title_txt}</title></line>'
                        )

                    # Place forward SNR label at 1/3 point
                    label_x_1 = start_x + (end_x - start_x) * 0.33
                    label_y_1 = start_y + (end_y - start_y) * 0.33
                    svg_parts.append(
                        f'<text x="{label_x_1:.1f}" y="{label_y_1 - 5:.1f}" text-anchor="middle" fill="#94a3b8" font-size="11">{_escape(snr_forward_txt)}</text>'
                    )

                    # If bidirectional, place reverse SNR label at 2/3 point
                    if has_reverse:
                        label_x_2 = start_x + (end_x - start_x) * 0.67
                        label_y_2 = start_y + (end_y - start_y) * 0.67
                        svg_parts.append(
                            f'<text x="{label_x_2:.1f}" y="{label_y_2 - 5:.1f}" text-anchor="middle" fill="#94a3b8" font-size="11">{_escape(snr_reverse_txt)}</text>'
                        )

                for node_id, (x, y) in node_positions.items():
                    is_reporter = node_id in reporter_nodes
                    fill, font_color = self.get_nodechip_colour(node_id)
                    stroke = 'white' if is_reporter else '#94a3b8'
                    stroke_width = 3 if is_reporter else 2

                    nd = visible_nodes.get(node_id) or {}
                    usr = nd.get('user') or {}
                    short_name = (usr.get('shortName') or node_id[-4:]).upper()
                    long_name = usr.get('longName') or ''

                    inner_label = _escape(short_name[:5])
                    name_label = _escape(long_name[:16]) if long_name else ''
                    title_txt = _escape(f'{node_id} | {long_name or short_name} | reporter={is_reporter}')

                    svg_parts.append(
                        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="28" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}"><title>{title_txt}</title></circle>'
                    )
                    if is_reporter:
                        svg_parts.append(
                            f'<text x="{x:.1f}" y="{y - 3:.1f}" text-anchor="middle" fill="{font_color}" font-size="16">🧭</text>'
                        )
                        svg_parts.append(
                            f'<text x="{x:.1f}" y="{y + 16:.1f}" text-anchor="middle" fill="{font_color}" font-size="10">{inner_label}</text>'
                        )
                    else:
                        svg_parts.append(
                            f'<text x="{x:.1f}" y="{y + 5:.1f}" text-anchor="middle" fill="{font_color}" font-size="12">{inner_label}</text>'
                        )
                    if name_label:
                        svg_parts.append(
                            f'<text x="{x:.1f}" y="{y + 44:.1f}" text-anchor="middle" fill="#94a3b8" font-size="10">{name_label}</text>'
                        )

                svg_parts.append('</svg>')
                ui.html(''.join(svg_parts)).classes('w-full')

                with ui.row().classes('w-full flex-wrap gap-x-6 gap-y-1 mt-2'):
                    ui.label('🧭 = node has reported neighbour info').classes('text-caption text-gray-500')
                    ui.label('Arrow direction = neighbour to reporter').classes('text-caption text-gray-500')
    
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
            # self.connection_manager.setup_comprehensive_hooks()
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
            # self.connection_manager.setup_comprehensive_hooks()
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

    # ── MQTT ──────────────────────────────────────────────────────────────

    def connect_mqtt(self) -> None:
        """Connect to the MQTT broker."""
        url = self.mqtt_host_input.value.strip()
        if not url:
            if self.mqtt_status:
                self.mqtt_status.text = 'MQTT: Enter broker URL'
            return
        username = self.mqtt_user_input.value.strip()
        password = self.mqtt_pass_input.value
        topic = self.mqtt_topic_input.value.strip() or '#'

        ok = self.mqtt_manager.connect(url, username, password, topic)
        if ok:
            self.mqtt_connected = True
            if self.mqtt_status:
                self.mqtt_status.text = f'MQTT: Connecting to {url} …'
            # Poll for actual connection status
            import asyncio

            async def _wait_connected():
                for _ in range(20):
                    await asyncio.sleep(0.5)
                    if self.mqtt_manager.is_connected():
                        if self.mqtt_status:
                            self.mqtt_status.text = f'MQTT: Connected to {url} [{topic}]'
                        return
                if not self.mqtt_manager.is_connected():
                    if self.mqtt_status:
                        self.mqtt_status.text = f'MQTT: Connection timeout'
                    self.mqtt_connected = False

            import asyncio
            asyncio.ensure_future(_wait_connected())
        else:
            self.mqtt_connected = False
            if self.mqtt_status:
                self.mqtt_status.text = 'MQTT: Connection failed (paho-mqtt not installed?)'

    def disconnect_mqtt(self) -> None:
        """Disconnect from the MQTT broker."""
        self.mqtt_manager.disconnect()
        self.mqtt_connected = False
        self.mqtt_nodes_data = {}
        self.neighbour_packets = self.mqtt_manager.get_neighbor_packets()
        if self.mqtt_status:
            self.mqtt_status.text = 'MQTT: Disconnected'
        self._update_nodes_display()
        self._update_neighbour_views()

    def _on_mqtt_update(self) -> None:
        """Called by MqttConnectionManager when new data arrives (background thread)."""
        self.mqtt_nodes_data = self.mqtt_manager.get_nodes_data()
        self.neighbour_packets = self.mqtt_manager.get_neighbor_packets()
        # Schedule UI update on the main thread
        try:
            from nicegui import background_tasks
            background_tasks.create(self._async_mqtt_refresh())
        except Exception:
            pass  # Will update on next manual/auto refresh

    async def _async_mqtt_refresh(self) -> None:
        """Async wrapper to update nodes display from MQTT data."""
        # Persist MQTT updates even when no manual refresh occurs.
        merged_for_persistence = dict(self.nodes_data)
        for nid, mqtt_node in self.mqtt_nodes_data.items():
            if nid not in merged_for_persistence:
                merged_for_persistence[nid] = mqtt_node
            else:
                existing = merged_for_persistence[nid]
                mqtt_last = int(mqtt_node.get('lastHeard', 0) or 0)
                existing_last = int(existing.get('lastHeard', 0) or 0)
                if mqtt_last > existing_last:
                    merged_for_persistence[nid] = {**existing, **mqtt_node, 'lastHeard': mqtt_last}
        if merged_for_persistence:
            self.data_persistence.save_nodes_data(merged_for_persistence)
        self.data_persistence.save_neighbour_packets(self.neighbour_packets)

        self._refresh_mqtt_reporters_ui()
        self._update_nodes_display()
        self._update_neighbour_views()
    
    def refresh_nodes(self) -> None:
        """Refresh the nodes display."""
        if self.connected and self.mesh_interface:
            # Refresh Meshtastic nodes data
            self.mesh_interface.refresh_nodes_data()
            self.mesh_interface.detect_last_heard_changes()
            self.mesh_interface.force_last_heard_update()
            self.nodes_data = self.mesh_interface.get_all_nodes_data()
            # Save data to persistence layer
            self.data_persistence.save_nodes_data(self.nodes_data)

        # Always pull latest MQTT nodes
        self.mqtt_nodes_data = self.mqtt_manager.get_nodes_data()
        self.neighbour_packets = self.mqtt_manager.get_neighbor_packets()
        self._refresh_mqtt_reporters_ui()

        # Persist merged data (Meshtastic + MQTT) so battery history captures both
        merged_for_persistence = dict(self.nodes_data)
        for nid, mqtt_node in self.mqtt_nodes_data.items():
            if nid not in merged_for_persistence:
                merged_for_persistence[nid] = mqtt_node
            else:
                existing = merged_for_persistence[nid]
                mqtt_last = int(mqtt_node.get('lastHeard', 0) or 0)
                existing_last = int(existing.get('lastHeard', 0) or 0)
                if mqtt_last > existing_last:
                    merged_for_persistence[nid] = {**existing, **mqtt_node, 'lastHeard': mqtt_last}
        if merged_for_persistence:
            self.data_persistence.save_nodes_data(merged_for_persistence)
        self.data_persistence.save_neighbour_packets(self.neighbour_packets)

        self._update_nodes_display()
        self._update_neighbour_views()
        # Update the node count display
        if hasattr(self, 'node_count_label'):
            self.node_count_label.update()
    
    def _update_nodes_display(self) -> None:
        """Update the nodes display with current data (Meshtastic + MQTT merged)."""
        self.nodes_container.clear()
        ui_text = self.config.get_ui_text().get('nodes', {})

        # Build merged view: Meshtastic nodes first, then MQTT-only nodes
        all_nodes: Dict[str, Any] = {}
        all_nodes.update(self.nodes_data)        # Meshtastic nodes
        for node_id, node in self.mqtt_nodes_data.items():
            if not self._is_node_visible_for_reporter(node):
                continue
            if node_id not in all_nodes:
                all_nodes[node_id] = node
            else:
                # Node exists in both — use the source with the more recent lastHeard for badge
                merged = all_nodes[node_id]
                mqtt_last = node.get('lastHeard', 0) or 0
                mesh_last = merged.get('lastHeard', 0) or 0
                if mqtt_last > mesh_last:
                    # MQTT heard this node more recently
                    merged['_mqtt_source'] = True
                    merged['lastHeard'] = mqtt_last
                else:
                    # Meshtastic is more recent — remove MQTT source badge
                    merged.pop('_mqtt_source', None)
                merged.pop('_from_persistence', None)

        if not all_nodes:
            with self.nodes_container:
                ui.label(ui_text.get('no_nodes_found', 'No nodes found')).classes('text-gray-500')
            return

        thirty_days_ago = int(time.time()) - 30 * 86400

        for node_id, node in all_nodes.items():
            # Skip nodes not heard in the last 30 days
            last_heard = int((node or {}).get('lastHeard') or 0)
            if last_heard > 0 and last_heard < thirty_days_ago:
                continue

            # Skip MQTT nodes when the toggle is off
            is_mqtt = node.get('_mqtt_source', False)
            is_persisted = node.get('_from_persistence', False)
            if (is_mqtt or (is_persisted and node_id not in self.nodes_data)) and not self.show_mqtt_nodes:
                continue

            if not self.show_all_nodes and 'isFavorite' not in node and not is_mqtt and not is_persisted:
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
        user = node.get('user') or {}
        short_name = user.get('shortName') or f"!{node_id[-8:]}"
        long_name = user.get('longName') or node_id
        hw_model = user.get('hwModel') or ui_text.get('unknown_hw', 'Unknown')
        is_mqtt = node.get('_mqtt_source', False)  # live MQTT packet received
        is_bridge = node.get('_is_bridge', False)
        is_persisted_only = node.get('_from_persistence', False) and not is_mqtt
        mqtt_topic = node.get('mqtt_topic', '')
        # Compact topic format: reported by <reporter>: <prefix>-<channel>
        topic_short = self._format_mqtt_topic_compact(mqtt_topic) if mqtt_topic else ''

        with ui.card().classes('w-full mb-1 py-1'):
            bg_color, font_color = self.get_nodechip_colour(node_id)
            label_classes = 'text-h6 text-white' if font_color == 'white' else 'text-h6'

            with ui.expansion(value=False).classes('w-full') as exp:
                with exp.add_slot('header'):  # Visible all the time
                    with ui.row().classes('w-full items-center justify-between'):
                        with ui.column().classes('items-start gap-0'):
                            with ui.row().classes('items-center gap-1'):
                                with ui.element('div').style(f'background-color: {bg_color};').classes('inline-block px-2 py-1 rounded mr-2'):
                                    ui.label(short_name).classes(label_classes).style(f'color: {font_color};')
                                ui.label(long_name).classes('text-h6')
                                if is_bridge:
                                    ui.html('<span title="MQTT Bridge">🌉</span>').classes('text-lg')
                                elif is_mqtt:
                                    ui.html('<span title="MQTT node">📡</span>').classes('text-sm')
                                elif is_persisted_only:
                                    ui.html('<span title="Cached from last session">💾</span>').classes('text-sm opacity-50')
                            if is_mqtt and topic_short:
                                ui.label(topic_short).classes('text-caption font-mono text-blue-300 ml-2')
                        with ui.row().classes('items-right'):
                            self.render_last_heard(node)
                            if 'deviceMetrics' in node:
                                self.render_battery_string(node, node_id=node_id)


                # The expansion content is the detailed view
                with ui.row().classes('w-full items-center justify-between flex-wrap gap-1'):
                    if 'deviceMetrics' in node:
                        metrics = node['deviceMetrics']
                        uptime_s = metrics.get('uptimeSeconds', 0)
                        uptime_hours = uptime_s / 3600 if uptime_s else 0
                        if self.mesh_interface and not node.get('_mqtt_source') and not node.get('_from_persistence'):
                            uptime_hours = self.mesh_interface.get_uptime(node, asString=False)
                        ui.label(f"up {uptime_hours:4.1f} hrs").classes('text-sm')
                        channel_util = metrics.get('channelUtilization', 0.0)
                        ui.label(f"{ui_text.get('channel_util_label', 'Channel Util')}: {channel_util:.1f}%").classes('text-caption')
                    ui.label(f"{ui_text.get('hw_label', 'HW')}: {hw_model}").classes('text-caption')
                    ui.label(f"{ui_text.get('user_id_label', 'User ID')}: {node_id}").classes('text-caption')
                    if is_mqtt:
                        badge = '🌉 MQTT Bridge' if is_bridge else '📡 MQTT'
                        with ui.column().classes('w-full gap-0 mt-1'):
                            ui.label(badge).classes('text-caption text-blue-400 font-bold')
                            if mqtt_topic:
                                ui.label(mqtt_topic).classes('text-caption font-mono text-gray-400')
                            rssi = node.get('mqtt_rssi')
                            snr = node.get('mqtt_snr')
                            if rssi is not None or snr is not None:
                                sig = ''
                                if rssi is not None:
                                    sig += f'RSSI: {rssi} dBm'
                                if snr is not None:
                                    sig += ('  ' if sig else '') + f'SNR: {snr} dB'
                                ui.label(sig).classes('text-caption text-gray-500')
                    elif is_persisted_only:
                        ui.label('💾 Cached — awaiting live data').classes('text-caption text-gray-500 mt-1')


    def _clear_nodes_display(self) -> None:
        """Clear the nodes display."""
        self.nodes_container.clear()
        ui_text = self.config.get_ui_text().get('nodes', {})
        with self.nodes_container:
            ui.label(ui_text.get('not_connected', 'Not connected')).classes('text-gray-500')
        # Reset node count display
        if hasattr(self, 'node_count_label'):
            self.node_count_label.update()

    def render_battery_string(self, node, node_id: str = ""):
        if self.mesh_interface and not node.get('_mqtt_source') and not node.get('_from_persistence'):
            battery_level, voltage, is_charging = self.mesh_interface.get_node_battery_status(node, asString=False)
        else:
            metrics = node.get('deviceMetrics', {})
            battery_level = int(metrics.get('batteryLevel', 0))
            voltage = float(metrics.get('voltage', 0.0))
            is_charging = battery_level == 101
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
                bat_color = "#C10015" 
            else:
                bat_color = "#21ba45"

            voltage_color = "#bbbbbb"
        else:
            # Light mode
            if is_charging:
                bat_color = "#1565c0" 
            elif battery_level < 60:
                bat_color = "#C10015"  # red
            else:
                bat_color = "#1b8d2b"  # more saturated green for better contrast

            voltage_color = "#666666"

        ding = ui.audio('assets/ding.mp3', controls=False)

        if battery_level < 60:
            # Avoid duplicate ongoing notifications for the same node by keying on shortName
            short_name = (node.get('user') or {}).get('shortName') or (f"!{node_id[-8:]}" if node_id else "Unknown")
            notif_key = f"lowbat_{short_name}"
            if not hasattr(self, '_lowbat_notifs'):
                self._lowbat_notifs = set()
            if notif_key not in self._lowbat_notifs:
                if battery_level < 30:
                    ui.notify(f"Node {short_name} Needs to be charged", type='ongoing', color='red', position='top', key=notif_key)
                else:
                    ui.notify(f"Node {short_name} Needs to be charged", type='negative')
                self._lowbat_notifs.add(notif_key)
            ui.run_javascript(f'getElement({ding.id}).$el.play()')


        return ui.html(
            f'<span class="text-sm">'
            f'<span style="color: {bat_color}; font-weight: bold;">{bat_str[:4]}</span>'
            f'<span style="color: {voltage_color};">{bat_str[4:]}</span>'
            f'</span>'
        )

    def render_last_heard(self, node):
        last_heard = int((node or {}).get('lastHeard') or 0)
        if last_heard <= 0:
            ui.html(
                f'<span class="text-sm" style="color:{"#bbbbbb" if self.dark.value else "#666666"};">Last Heard:<br>Unknown</span>'
            )
            return
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
    
    def _get_time_label(self, days: float) -> str:
        """Generate appropriate time label for the given number of days."""
        if days < 1:
            if days == 0.042:  # 1 hour
                return "1 Hour"
            elif days == 0.25:  # 6 hours
                return "6 Hours"
            elif days == 0.5:  # 12 hours
                return "12 Hours"
            else:
                return f"{days*24:.1f} Hours"
        else:
            return f"{days} Days"
    
    def update_battery_chart(self) -> None:
        """Update the battery history chart."""
        try:
            # Get data
            days = self.days_selector.value
            df = self.data_persistence.get_battery_history(days)
            print(f"DEBUG: Days selected: {days}")
            print(f"DEBUG: Raw data shape: {df.shape}")
            if not df.empty:
                print(f"DEBUG: Available nodes: {df['node_id'].unique()}")
                print(f"DEBUG: Data sample: {df[['timestamp', 'node_id', 'short_name', 'voltage', 'battery_level']].head()}")
            
            # Update node selector options
            if not df.empty:
                unique_nodes = df['node_id'].unique()
                node_options = {}
                from datetime import datetime, timedelta
                now = datetime.now()
                week_ago = now - timedelta(days=7)
                for node_id in unique_nodes:
                    node_df = df[df['node_id'] == node_id]
                    short_name = node_df.iloc[0]['short_name']
                    # Filter for last 7 days for this node
                    node_week = node_df[node_df['timestamp'] >= week_ago]
                    if not node_week.empty:
                        min_week_volt = node_week['voltage'].min()
                        min_week_batt = node_week['battery_level'].min()
                        # Determine color class based on thresholds
                        if min_week_batt < 30:
                            symbol = "🔴"  # Red circle
                        elif min_week_batt < 60:
                            symbol = "🟡"  # Yellow circle
                        else:
                            symbol = "🟢"  # Green circle
                        # Use Unicode symbols for battery percent
                        label = f"{short_name} (!{node_id[-8:]}) - Battery Low (7d): {min_week_batt:.0f}% {symbol}"
                    else:
                        label = f"{short_name} (!{node_id[-8:]})"
                    node_options[node_id] = label
                self.node_selector.options = node_options
                # Only set default if no node is currently selected
                if not self.node_selector.value and node_options:
                    self.node_selector.value = list(node_options.keys())[0]
            
            # Clear containers
            self.battery_chart_container.clear()
            self.data_summary_container.clear()
            self.battery_chart = None  # Reset chart reference
            print("DEBUG: Containers cleared and chart reset")
            
            if df.empty:
                # Show empty chart with full timespan
                fig = go.Figure()
                
                # Calculate the full timespan for the selected period
                from datetime import datetime, timedelta
                end_time = datetime.now()
                start_time = end_time - timedelta(days=days)
                
                # Add empty traces to show the axes
                fig.add_trace(go.Scatter(
                    x=[],
                    y=[],
                    mode='markers+lines',
                    name='Voltage (V)',
                    line=dict(color='#21BA45', width=2),
                    marker=dict(size=6, color='#21BA45', line=dict(width=1, color='white'))
                ))
                
                fig.add_trace(go.Scatter(
                    x=[],
                    y=[],
                    mode='markers+lines',
                    name='Battery Level (%)',
                    yaxis='y2',
                    line=dict(color='#C10015', width=2),
                    marker=dict(size=6, color='#C10015', line=dict(width=1, color='white'))
                ))
                
                # Update layout with full timespan and reasonable default ranges
                fig.update_layout(
                    title=f'Battery History - {self._get_time_label(days)} (No Data)',
                    xaxis_title='Time',
                    yaxis=dict(
                        title='Voltage (V)', 
                        side='left',
                        range=[3.0, 4.5],  # Typical battery voltage range
                        tickformat='.3f'
                    ),
                    yaxis2=dict(
                        title='Battery Level (%)', 
                        side='right', 
                        overlaying='y',
                        range=[0, 100],  # Battery percentage range
                        tickformat='.0f'
                    ),
                    hovermode='x unified',
                    template='plotly_dark' if self.dark.value else 'plotly_white',
                    height=500,
                    xaxis=dict(
                        range=[start_time, end_time],
                        showgrid=True,
                        gridwidth=1,
                        gridcolor='rgba(128,128,128,0.2)'
                    ),
                    showlegend=True,
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="right",
                        x=1
                    )
                )
                
                with self.battery_chart_container:
                    ui.plotly(fig).classes('w-full')
                with self.data_summary_container:
                    ui.label('No battery data available for the selected time period').classes('text-gray-500 text-center')
                return
            
            # Filter by selected node if specified
            selected_node = self.node_selector.value
            print(f"DEBUG: Selected node: {selected_node}")
            print(f"DEBUG: Data shape before filtering: {df.shape}")
            if selected_node:
                df = df[df['node_id'] == selected_node]
                print(f"DEBUG: Data shape after filtering: {df.shape}")
                
                # Remove duplicates - keep the latest entry for each timestamp
                df = df.drop_duplicates(subset=['timestamp'], keep='last')
                print(f"DEBUG: Data shape after deduplication: {df.shape}")
                
                if not df.empty:
                    print(f"DEBUG: Filtered data sample: {df[['timestamp', 'node_id', 'short_name', 'voltage', 'battery_level']].head()}")
            
            # if df.empty:
            if False:
                # Show empty chart with full timespan for selected node
                fig = go.Figure()
                
                # Calculate the full timespan for the selected period
                from datetime import datetime, timedelta
                end_time = datetime.now()
                start_time = end_time - timedelta(days=days)
                
                # Add empty traces to show the axes
                fig.add_trace(go.Scatter(
                    x=[],
                    y=[],
                    mode='markers+lines',
                    name='Voltage (V)',
                    line=dict(color='#21BA45', width=2),
                    marker=dict(size=6, color='#21BA45', line=dict(width=1, color='white'))
                ))
                
                fig.add_trace(go.Scatter(
                    x=[],
                    y=[],
                    mode='markers+lines',
                    name='Battery Level (%)',
                    yaxis='y2',
                    line=dict(color='#C10015', width=2),
                    marker=dict(size=6, color='#C10015', line=dict(width=1, color='white'))
                ))
                
                # Get node name for title
                node_name = "Unknown Node"
                if selected_node:
                    # Try to get node name from the original data
                    all_data = self.data_persistence.get_battery_history(days)
                    if not all_data.empty:
                        node_data = all_data[all_data['node_id'] == selected_node]
                        if not node_data.empty:
                            node_name = node_data.iloc[0]['short_name']
                
                # Update layout with full timespan and reasonable default ranges
                fig.update_layout(
                    title=f'Battery History - {self._get_time_label(days)} - {node_name} (No Data)',
                    xaxis_title='Time',
                    yaxis=dict(
                        title='Voltage (V)', 
                        side='left',
                        range=[3.0, 4.5],  # Typical battery voltage range
                        tickformat='.3f'
                    ),
                    yaxis2=dict(
                        title='Battery Level (%)', 
                        side='right', 
                        overlaying='y',
                        range=[0, 100],  # Battery percentage range
                        tickformat='.0f'
                    ),
                    hovermode='x unified',
                    template='plotly_dark' if self.dark.value else 'plotly_white',
                    height=500,
                    xaxis=dict(
                        range=[start_time, end_time],
                        showgrid=True,
                        gridwidth=1,
                        gridcolor='rgba(128,128,128,0.2)'
                    ),
                    showlegend=True,
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="right",
                        x=1
                    )
                )
                
                with self.battery_chart_container:
                    ui.plotly(fig).classes('w-full')
                with self.data_summary_container:
                    ui.label(f'No data available for {node_name} in the selected time period').classes('text-gray-500 text-center')
                return
            
            # Create battery voltage chart
            fig = go.Figure()
            
            # Calculate the full timespan for the selected period
            from datetime import datetime, timedelta
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)
            
            # Debug: Print the actual data being plotted
            print(f"DEBUG: Plotting {len(df)} data points")
            print(f"DEBUG: Voltage range: {df['voltage'].min():.3f}V to {df['voltage'].max():.3f}V")
            print(f"DEBUG: Battery range: {df['battery_level'].min():.0f}% to {df['battery_level'].max():.0f}%")
            print(f"DEBUG: Time range: {df['timestamp'].min()} to {df['timestamp'].max()}")

            print("DEBUG: Voltage values:")
            print(df['voltage'].tolist())
            print("DEBUG: Battery level values:")
            print(df['battery_level'].tolist())
            print("DEBUG: Timestamps:")
            print(df['timestamp'].tolist())
            print("DEBUG: Checking for duplicates:")
            print(f"DEBUG: Total rows: {len(df)}")
            print(f"DEBUG: Unique timestamps: {df['timestamp'].nunique()}")
            print(f"DEBUG: Duplicate timestamps: {df['timestamp'].duplicated().sum()}")
            if df['timestamp'].duplicated().any():
                print("DEBUG: Duplicate timestamps found:")
                print(df[df['timestamp'].duplicated(keep=False)].sort_values('timestamp'))
            
            # Add voltage line with points
            fig.add_trace(go.Scatter(
                x=df['timestamp'],
                y=df['voltage'].tolist(),
                mode='markers+lines',
                name='Voltage (V)',
                line=dict(color='#21BA45', width=2),
                marker=dict(size=6, color='#21BA45', line=dict(width=1, color='#21BA45')),
                connectgaps=False
            ))
            
            # Add battery level as secondary y-axis with points
            fig.add_trace(go.Scatter(
                x=df['timestamp'],
                y=df['battery_level'].tolist(),
                mode='markers+lines',
                name='Battery Level (%)',
                yaxis='y2',
                line=dict(color='#C10015', width=2),
                marker=dict(size=6, color='#C10015', line=dict(width=1, color='#C10015')),
                connectgaps=False
            ))
            
            # Use consistent axis ranges regardless of data
            voltage_range = [3.0, 4.5]  # Fixed voltage range
            battery_range = [0, 100]    # Fixed battery percentage range
            
            # Update layout with full timespan and proper axis ranges
            fig.update_layout(
                title=f'Battery History - {self._get_time_label(days)}' + (f' - {df.iloc[0]["short_name"]}' if selected_node else ''),
                xaxis_title='Time',
                yaxis=dict(
                    title='Voltage (V)', 
                    side='left',
                    range=voltage_range,
                    tickformat='.3f'
                ),
                yaxis2=dict(
                    title='Battery Level (%)', 
                    side='right', 
                    overlaying='y',
                    range=battery_range,
                    tickformat='.0f'
                ),
                hovermode='x unified',
                template='plotly_dark' if self.dark.value else 'plotly_white',
                height=500,
                xaxis=dict(
                    range=[start_time, end_time],
                    # range=[0, 8],
                    showgrid=True,
                    gridwidth=1,
                    gridcolor='rgba(128,128,128,0.2)'
                ),
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
                        
            # Display chart
            with self.battery_chart_container:
                # Always create a new chart to ensure it updates
                self.battery_chart = ui.plotly(fig).classes('w-full')
                print(f"DEBUG: Chart created/updated with {len(df)} data points")
            
            # Display data summary
            with self.data_summary_container:
                with ui.row().classes('w-full gap-4'):
                    with ui.card().classes('flex-1'):
                        ui.label('Data Summary').classes('text-h6')
                        ui.label(f'Records: {len(df)}').classes('text-sm')
                        ui.label(f'Date Range: {df["timestamp"].min().strftime("%Y-%m-%d %H:%M")} to {df["timestamp"].max().strftime("%Y-%m-%d %H:%M")}').classes('text-sm')
                    
                    with ui.card().classes('flex-1'):
                        ui.label('Voltage Stats').classes('text-h6')
                        ui.label(f'Min: {df["voltage"].min():.3f}V').classes('text-sm')
                        ui.label(f'Max: {df["voltage"].max():.3f}V').classes('text-sm')
                        ui.label(f'Avg: {df["voltage"].mean():.3f}V').classes('text-sm')
                    
                    with ui.card().classes('flex-1'):
                        ui.label('Battery Stats').classes('text-h6')
                        ui.label(f'Min: {df["battery_level"].min():.0f}%').classes('text-sm')
                        ui.label(f'Max: {df["battery_level"].max():.0f}%').classes('text-sm')
                        ui.label(f'Avg: {df["battery_level"].mean():.0f}%').classes('text-sm')
                        
        except Exception as e:
            print(f"Error updating battery chart: {e}")
            with self.battery_chart_container:
                ui.label(f'Error loading chart: {str(e)}').classes('text-red-500 text-center')
    
    def run(self, **kwargs) -> None:
        """Run the GUI application."""
        self.setup_ui()
        ui.run(**kwargs)
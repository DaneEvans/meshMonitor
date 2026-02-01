"""
Meshtastic connection management module.
"""
try:
    import meshtastic
    import meshtastic.tcp_interface
    import meshtastic.serial_interface
    from pubsub import pub
except ImportError:
    # Handle case where meshtastic library is not installed
    meshtastic = None
    pub = None
    
import time
import threading
from dataclasses import dataclass
from typing import Optional, Callable, Any, List, Dict

from .config import ConfigManager


@dataclass
class AutoMessage:
    """A scheduled auto-message."""

    interval_s: float  # interval in seconds
    channel: int
    msg: str
    # Last minute (epoch minutes) when this message was sent, used with modulo scheduling.
    last_sent_minute: Optional[int] = None


class MeshConnectionManager:
    """Manages Meshtastic network connections."""

    # Keep a small, explicit allowlist for GUI selection (session-only overrides)
    SUPPORTED_TAPBACK_EMOJIS = ["🤖", "✅", "👍"]
    
    def __init__(self, cfg: Optional[ConfigManager] = None, config_path: Optional[str] = None):
        """Initialize the connection manager.

        Args:
            cfg: Optional existing ConfigManager instance to reuse.
            config_path: Optional path to config file (used if `cfg` is None).
        """
        self.interface: Optional[Any] = None
        self.connection_type: Optional[str] = None
        self.connection_params: Optional[dict] = None
        self.tapback_sent: set = set()  # Track message IDs that have already received tapbacks

        # Use provided ConfigManager if given, otherwise construct one (optionally with config_path)
        if cfg is not None:
            self.config = cfg
        else:
            self.config = ConfigManager(config_path) if config_path is not None else ConfigManager()

        # Load tapback emoji from config (default to robot to preserve behaviour)
        self.tapback_emoji: str = self.config.get("notifications.auto_emoji", "🤖")
        self.enable_auto_react: bool = self.config.get("notifications.enable_auto_react", True)

        # Auto-message (scheduled broadcast) settings
        self.enable_auto_message: bool = bool(self.config.get("automessage.enabled", False))
        self._auto_messages: List[AutoMessage] = self._parse_auto_messages(self.config.get("automessage.messages", []))

        # Background worker for auto-messages (only runs in this process; not persisted)
        self._auto_message_lock = threading.Lock()
        self._auto_message_stop = threading.Event()
        self._auto_message_thread: Optional[threading.Thread] = None

    def set_auto_react_enabled(self, enabled: bool) -> None:
        """Enable/disable automatic emoji reactions (runtime only)."""
        self.enable_auto_react = bool(enabled)

    def set_tapback_emoji(self, emoji: str) -> None:
        """Set the tapback emoji (runtime only)."""
        if emoji in self.SUPPORTED_TAPBACK_EMOJIS:
            self.tapback_emoji = emoji

    def get_auto_messages(self) -> List[Dict[str, Any]]:
        """Get current auto-messages (runtime view for UI)."""
        with self._auto_message_lock:
            return [
                {
                    "interval": m.interval_s / 60.0,
                    "channel": m.channel,
                    "msg": m.msg,
                    "enabled": True,
                }
                for m in self._auto_messages
            ]

    def set_auto_message_enabled(self, enabled: bool) -> None:
        """Enable/disable scheduled auto-messages (runtime only)."""
        with self._auto_message_lock:
            self.enable_auto_message = bool(enabled)
        if self.enable_auto_message and self.is_connected():
            self._ensure_auto_message_thread()

    def set_auto_messages(self, messages: Any) -> None:
        """Replace scheduled auto-messages (runtime only)."""
        parsed = self._parse_auto_messages(messages)
        with self._auto_message_lock:
            self._auto_messages = parsed
        if self.enable_auto_message and self.is_connected():
            self._ensure_auto_message_thread()

    def _parse_auto_messages(self, raw: Any) -> List[AutoMessage]:
        """Parse config/UI messages list into AutoMessage objects."""
        # Preserve schedule alignment for existing messages where possible.
        prev_by_key: Dict[tuple, AutoMessage] = {}
        for m in getattr(self, "_auto_messages", []):
            key = (round(m.interval_s / 60.0, 3), m.channel, m.msg)
            prev_by_key[key] = m

        if not raw:
            return []
        if not isinstance(raw, list):
            return []

        out: List[AutoMessage] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            # Accept multiple key spellings; config uses `interval` in minutes.
            interval_mins = item.get("interval", item.get("interval_mins", item.get("intervalMinutes")))
            channel = item.get("channel", 0)
            msg = item.get("msg", item.get("message", ""))
            enabled = bool(item.get("enabled", True))

            try:
                interval_mins_f = float(interval_mins)
            except (TypeError, ValueError):
                continue
            if interval_mins_f <= 0:
                continue

            try:
                channel_i = int(channel)
            except (TypeError, ValueError):
                channel_i = 0
            if channel_i < 0:
                channel_i = 0

            msg_s = str(msg).strip()
            if not msg_s or not enabled:
                continue

            key = (interval_mins_f, channel_i, msg_s)
            prev = prev_by_key.get(key)
            last_sent_minute = prev.last_sent_minute if prev else None

            out.append(
                AutoMessage(
                    interval_s=interval_mins_f * 60.0,
                    channel=channel_i,
                    msg=msg_s,
                    last_sent_minute=last_sent_minute,
                )
            )

        return out

    def _ensure_auto_message_thread(self) -> None:
        """Start auto-message worker thread if needed."""
        if self._auto_message_thread and self._auto_message_thread.is_alive():
            return
        self._auto_message_stop.clear()
        self._auto_message_thread = threading.Thread(
            target=self._auto_message_worker,
            name="meshmonitor-auto-message",
            daemon=True,
        )
        self._auto_message_thread.start()

    def _stop_auto_message_thread(self) -> None:
        """Stop auto-message worker thread."""
        self._auto_message_stop.set()
        t = self._auto_message_thread
        if t and t.is_alive():
            t.join(timeout=1.0)
        self._auto_message_thread = None

    def _auto_message_worker(self) -> None:
        """Background worker that sends scheduled messages."""
        while not self._auto_message_stop.is_set():
            # Fast check without holding the lock during I/O.
            with self._auto_message_lock:
                enabled = bool(self.enable_auto_message)
                messages = list(self._auto_messages)

            if not enabled or not self.is_connected():
                # Sleep lightly; wait() allows quicker shutdown.
                self._auto_message_stop.wait(1.0)
                continue

            now_ts = time.time()
            now_minute = int(now_ts // 60)
            for m in messages:
                # If message list was replaced, this object might be stale; that's OK.
                interval_mins = max(1, int(round(m.interval_s / 60.0)))  # at least every 1 minute

                # Align send time to minute boundaries: only send when (minutes % interval) == 0
                if interval_mins <= 0 or (now_minute % interval_mins) != 0:
                    continue
                # Already sent in this minute
                if m.last_sent_minute == now_minute:
                    continue
                # Send broadcast on a specific channel index.
                ok = self.send_text(m.msg, channel_index=m.channel)
                # Avoid rapid retries; remember the minute in which we sent.
                m.last_sent_minute = now_minute
                if ok:
                    print(f"INFO: AutoMessage sent | ch:{m.channel} | every:{m.interval_s/60.0:g}m | {m.msg}")

            self._auto_message_stop.wait(1.0)
        
    def connect_tcp(self, host: str, port: int = 4403) -> bool:
        """
        Connect to Meshtastic network via TCP.
        
        Args:
            host: TCP host address
            port: TCP port (default: 4403)
            
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.interface = meshtastic.tcp_interface.TCPInterface(host)
            self.connection_type = "tcp"
            self.connection_params = {"host": host, "port": port}
            
            # Give the interface a moment to initialize
            time.sleep(0.5)
            if self.enable_auto_message:
                self._ensure_auto_message_thread()
            return True
        except Exception as e:
            print(f"TCP connection failed: {e}")
            return False
    
    def connect_serial(self, port: Optional[str] = None) -> bool:
        """
        Connect to Meshtastic network via Serial.
        
        Args:
            port: Serial port (auto-detect if None)
            
        Returns:
            True if connection successful, False otherwise
        """
        try:
            if not meshtastic:
                print("Meshtastic library not available")
                return False
                
            if port:
                self.interface = meshtastic.serial_interface.SerialInterface(port)
            else:
                self.interface = meshtastic.serial_interface.SerialInterface()
            self.connection_type = "serial"
            self.connection_params = {"port": port}
            
            # Give the interface a moment to initialize
            time.sleep(0.5)
            if self.enable_auto_message:
                self._ensure_auto_message_thread()
            return True
        except Exception as e:
            print(f"Serial connection failed: {e}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from the Meshtastic network."""
        self._stop_auto_message_thread()
        if self.interface:
            try:
                self.interface.close()
            except Exception as e:
                print(f"Error during disconnect: {e}")
            finally:
                self.interface = None
                self.connection_type = None
                self.connection_params = None
    
    def is_connected(self) -> bool:
        """
        Check if currently connected to the network.
        
        Returns:
            True if connected, False otherwise
        """
        return self.interface is not None
    
    def get_interface(self):
        """
        Get the current interface.
        
        Returns:
            The current Meshtastic interface or None
        """
        return self.interface
    
    def setup_callbacks(self, on_receive: Optional[Callable] = None, 
                       on_connection: Optional[Callable] = None,
                       on_telemetry: Optional[Callable] = None,
                       on_text: Optional[Callable] = None) -> None:
        """
        Setup callback functions for packet reception and connection events.
        
        Args:
            on_receive: Function to call when a packet is received
            on_connection: Function to call when connection is established
            on_telemetry: Function to call when telemetry data is received
            on_text: Function to call when a text message is received
        """
        if not pub:
            print("PubSub library not available")
            return
            
        if on_receive:
            pub.subscribe(on_receive, "meshtastic.receive")
        if on_connection:
            pub.subscribe(on_connection, "meshtastic.connection.established")
        if on_telemetry:
            pub.subscribe(on_telemetry, "meshtastic.telemetry.receive")
        if on_text:
            pub.subscribe(on_text, "meshtastic.receive.text")
    
    def enable_auto_refresh(self) -> None:
        """
        Enable automatic refresh of node data when packets are received.
        This sets up multiple callbacks to handle different packet types.
        """
        if not self.interface:
            return
        
        def update_last_heard(packet, interface, packet_type=""):
            """Helper function to update lastHeard timestamp for any packet type."""
            try:
                if packet and 'from' in packet:
                    from_node = packet['from']
                    current_time = int(time.time())
                    
                    # Handle both integer node numbers and string node IDs
                    if isinstance(from_node, int):
                        node_id = f"!{from_node:08x}"
                    else:
                        node_id = from_node
                    print(f"update_last_heard: {node_id}")

                    # Update the lastHeard timestamp in the interface's nodes dict
                    if hasattr(interface, 'nodes') and node_id in interface.nodes:
                        interface.nodes[node_id]['lastHeard'] = current_time
                        
            except Exception:
                # Don't let packet processing errors break the callback
                pass
        
        def on_packet_received(packet, interface):  # pylint: disable=unused-argument
            """Callback function called when a general packet is received."""
            print(f"DEBUG: on_packet_received called (connection_type: {self.connection_type})")
            update_last_heard(packet, interface, "general")
        
        def on_telemetry_received(packet, interface):  # pylint: disable=unused-argument
            """Callback function called when telemetry data is received."""
            print(f"DEBUG: on_telemetry_received called")
            update_last_heard(packet, interface, "telemetry")
        
        def on_text_received(packet, interface):  # pylint: disable=unused-argument
            """Callback function called when a text message is received."""
            print(f"DEBUG: on_text_received called (connection_type: {self.connection_type})")
            if packet and isinstance(packet, dict) and 'decoded' in packet:
                decoded = packet['decoded']
                if isinstance(decoded, dict) and 'text' in decoded:
                    text_content = decoded['text']
                    update_last_heard(packet, interface, "text")

                    # Extract message ID and sender from packet
                    message_id = packet.get('id', None)
                    from_node = packet.get('from', None)
                    to_node = packet.get('to', None)

                    channel = packet.get("channel", "Primary")
                    # Check if it's a DM - if 'to' is not '0xFFFFFF', treat as DM
                    if to_node is not None and to_node != 4294967295:
                        channel = "DM"

                    print(f"INFO: Text rx | ch:{channel} | {text_content}")

                    # Helper to derive node ID from from_node for replies
                    def _node_id_from_from_node(node_num_or_id):
                        if isinstance(node_num_or_id, int):
                            return f"!{node_num_or_id:08x}"
                        return node_num_or_id

                    # Handle DM control commands: 'reply on' / 'reply off' / 'help' (case-insensitive)
                    if channel == "DM":
                        cmd = text_content.strip().lower()
                        if cmd == "reply on":
                            self.enable_auto_react = True
                            msg = "Auto react ENABLED via DM command"
                            print(f"INFO: {msg}")
                            # Send confirmation back as a reply
                            dest_id = _node_id_from_from_node(from_node)
                            if message_id is not None and dest_id is not None:
                                self.send_text(msg, dest_id)
                            return
                        if cmd == "reply off":
                            self.enable_auto_react = False
                            msg = "Auto react DISABLED via DM command"
                            print(f"INFO: {msg}")
                            # Send confirmation back as a reply
                            dest_id = _node_id_from_from_node(from_node)
                            if message_id is not None and dest_id is not None:
                                self.send_text(msg, dest_id)
                            return
                        if cmd == "help":
                            help_text = (
                                "MeshMonitor commands:\n"
                                " - reply on  : enable automatic emoji reactions\n"
                                " - reply off : disable automatic emoji reactions\n"
                                " - help      : show this help message"
                            )
                            print("INFO: DM help requested, sending help text")
                            dest_id = _node_id_from_from_node(from_node)
                            if message_id is not None and dest_id is not None:
                                self.send_text(help_text, dest_id)
                            return

                    # Do not auto reply to other DMs. 
                    if channel == "DM":
                        print(f"DEBUG: Skipping DM message to {to_node}")
                        return

                    # Check if this is already an emoji reaction (skip replies for emoji messages)
                    is_emoji_reaction = decoded.get('emoji', 0) != 0
                    if is_emoji_reaction:
                        return
                    
                    # Check if we've already replied to this message
                    if message_id is not None and message_id in self.tapback_sent:
                        return

                    # Send both emoji tapback and text reply separately
                    if message_id is not None and packet.get("channel", 0) != 0 and self.enable_auto_react:  # don't reply to channel 0, honour config
                        # Verify connection is still active before sending (especially important for TCP)
                        if not self.is_connected() or self.interface is None:
                            print(f"DEBUG: Connection lost, skipping reply (connection_type: {self.connection_type})")
                            return
                        try:
                            # Use emoji in config.yaml for tapback
                            self.send_tapback(self.tapback_emoji, message_id, from_node)
                            # time.sleep(5)
                            # self.send_text_reply("hello mesh", message_id, from_node)
                            # Mark as replied
                            self.tapback_sent.add(message_id)
                        except (SystemExit, KeyboardInterrupt):
                            # Re-raise these critical exceptions
                            raise
                        except Exception as e:
                            # Catch all other exceptions to prevent breaking PubSub callback chain
                            # This is critical for TCP interfaces
                            print(f"Failed to send reply in PubSub callback: {e}")
                            import traceback
                            traceback.print_exc()
        
        # Store callback reference for direct invocation
        self._text_callback = on_text_received
        
        # Set up callbacks for different packet types
        self.setup_callbacks(
            on_receive=on_packet_received,
            on_telemetry=on_telemetry_received,
            on_text=on_text_received
        )    
    
    def send_text(self, text: str, destination_id: Optional[str] = None, channel_index: Optional[int] = None) -> bool:
        """
        Send text message to the network.
        
        Args:
            text: Text message to send
            destination_id: Destination node ID (broadcast if None)
            channel_index: Meshtastic channel index (0 = Primary). If None, uses library default.
            
        Returns:
            True if message sent successfully, False otherwise
        """
        if not self.is_connected():
            return False
        
        try:
            if self.interface is None:
                return False

            kwargs: Dict[str, Any] = {}
            if channel_index is not None:
                try:
                    kwargs["channelIndex"] = int(channel_index)
                except (TypeError, ValueError):
                    pass

            if destination_id:
                # Prefer keyword args for compatibility across meshtastic versions.
                if kwargs:
                    self.interface.sendText(text, destination_id, **kwargs)
                else:
                    self.interface.sendText(text, destination_id)
            else:
                if kwargs:
                    self.interface.sendText(text, **kwargs)
                else:
                    self.interface.sendText(text)
            return True
        except TypeError:
            # Fallback if the installed meshtastic doesn't accept channelIndex
            try:
                if destination_id:
                    self.interface.sendText(text, destination_id)
                else:
                    self.interface.sendText(text)
                return True
            except Exception as e:
                print(f"Failed to send text: {e}")
                return False
        except Exception as e:
            print(f"Failed to send text: {e}")
            return False
    
    def send_text_reply(self, text: str, reply_to_message_id: int, destination_id: Optional[str] = None) -> bool:
        """
        Send a text message reply with reply_id set in the decoded Data structure.
        
        Args:
            text: Text message to send
            reply_to_message_id: ID of the message being replied to
            destination_id: Destination node ID (broadcast if None)
            
        Returns:
            True if message sent successfully, False otherwise
        """
        if not self.is_connected():
            return False
        
        try:
            from meshtastic import mesh_pb2, portnums_pb2
            
            # Create a Data message with reply_id
            data = mesh_pb2.Data()
            data.payload = text.encode('utf-8')
            data.reply_id = reply_to_message_id
            
            # Create a MeshPacket with the decoded Data
            packet = mesh_pb2.MeshPacket()
            packet.decoded.CopyFrom(data)
            packet.decoded.portnum = portnums_pb2.TEXT_MESSAGE_APP
            packet.want_ack = False
            
            # Set destination if specified
            if destination_id:
                # Convert destination_id (node ID) to node number if needed
                dest_num = None
                if hasattr(self.interface, 'nodes') and destination_id in self.interface.nodes:
                    node_info = self.interface.nodes[destination_id]
                    if isinstance(node_info, dict) and 'num' in node_info:
                        dest_num = node_info['num']
                
                if dest_num is not None:
                    packet.to = dest_num
                        
            self.interface._sendPacket(packet)
            return True
        except Exception as e:
            print(f"Failed to send text reply: {e}")
            return False
    
    def send_tapback(self, emoji: str, message_id: int, destination_id: Optional[str] = None) -> bool:
        """
        Send a tapback/reaction emoji to a message.
        Follows the Android implementation structure exactly.
        
        Args:
            emoji: Emoji character to send as reaction
            message_id: ID of the message to react to
            destination_id: Destination node ID (broadcast if None)
            
        Returns:
            True if tapback sent successfully, False otherwise
        """
        if not self.is_connected():
            return False
        
        # Check if we've already sent a tapback to this message
        if message_id in self.tapback_sent:
            return False
        
        try:
            from meshtastic import mesh_pb2, portnums_pb2
            
            # Map emoji characters to their emoji numbers and payload bytes
            # Robot emoji 🤖 = 129302 (decimal HTML entity)
            # Payload bytes: \xF0\x9F\xA4\x96 (UTF-8 encoding of U+1F916)
            emoji_configs = {
                "🤖": {
                    "number": 129302,
                    "payload": b'\xF0\x9F\xA4\x96'  # 🤖
                },
                "✅": {
                    "number": 9989,
                    "payload": b'\xE2\x9C\x85'      # ✅
                },
                "👍": {
                    "number": 128077,
                    "payload": b'\xF0\x9F\x91\x8D'  # 👍
                }
            }
            
            # Get emoji config, default to robot if not found
            if emoji in emoji_configs:
                emoji_config = emoji_configs[emoji]
                emoji_number = emoji_config["number"]
                emoji_payload = emoji_config["payload"]
            else:
                # Default to robot emoji
                emoji_number = 129302
                emoji_payload = b'\xF0\x9F\xA4\x96'
            
            data = mesh_pb2.Data()
            data.payload = emoji_payload  # Emoji bytes
            data.reply_id = message_id  # ID of message being reacted to
            data.emoji = emoji_number  # Emoji number (e.g., 129302 for robot)
            
            # Create a MeshPacket with the decoded Data
            packet = mesh_pb2.MeshPacket()
            packet.decoded.CopyFrom(data)
            packet.decoded.portnum = portnums_pb2.TEXT_MESSAGE_APP  # Set portnum on decoded
            packet.want_ack = False
            
            # Convert destination_id to node number if needed
            dest_num = None
            if destination_id:
                if hasattr(self.interface, 'nodes') and destination_id in self.interface.nodes:
                    node_info = self.interface.nodes[destination_id]
                    if isinstance(node_info, dict) and 'num' in node_info:
                        dest_num = node_info['num']                
                if dest_num is not None:
                    packet.to = dest_num
            
            self.interface._sendPacket(packet)
        except Exception as e:
            print(f"Failed to send tapback: {e}")
            return False

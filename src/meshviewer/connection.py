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
from typing import Optional, Callable, Any


class MeshConnectionManager:
    """Manages Meshtastic network connections."""
    
    def __init__(self):
        """Initialize the connection manager."""
        self.interface: Optional[Any] = None
        self.connection_type: Optional[str] = None
        self.connection_params: Optional[dict] = None
        self.tapback_sent: set = set()  # Track message IDs that have already received tapbacks
        
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
            
            return True
        except Exception as e:
            print(f"Serial connection failed: {e}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from the Meshtastic network."""
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

                    # Do not auto reply to a DM. 
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
                    if message_id is not None and packet.get("channel", 0) != 0: # don't reply to channel 0
                        # Verify connection is still active before sending (especially important for TCP)
                        if not self.is_connected() or self.interface is None:
                            print(f"DEBUG: Connection lost, skipping reply (connection_type: {self.connection_type})")
                            return
                        try:
                            self.send_tapback("🤖", message_id, from_node)
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
    
    def send_text(self, text: str, destination_id: Optional[str] = None) -> bool:
        """
        Send text message to the network.
        
        Args:
            text: Text message to send
            destination_id: Destination node ID (broadcast if None)
            
        Returns:
            True if message sent successfully, False otherwise
        """
        if not self.is_connected():
            return False
        
        try:
            if destination_id:
                self.interface.sendText(text, destination_id)
            else:
                self.interface.sendText(text)
            return True
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
                    "payload": b'\xF0\x9F\xA4\x96'  # UTF-8 bytes: \360\237\244\226
                },
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

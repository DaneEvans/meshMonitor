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
                       on_telemetry: Optional[Callable] = None) -> None:
        """
        Setup callback functions for packet reception and connection events.
        
        Args:
            on_receive: Function to call when a packet is received
            on_connection: Function to call when connection is established
            on_telemetry: Function to call when telemetry data is received
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
    
    def enable_auto_refresh(self) -> None:
        """
        Enable automatic refresh of node data when packets are received.
        This sets up multiple callbacks to handle different packet types.
        """
        def update_last_heard(packet, interface, packet_type=""):
            """Helper function to update lastHeard timestamp for any packet type."""
            try:
                if packet and 'from' in packet:
                    node_id = packet['from']
                    current_time = int(time.time())
                    timestamp = time.strftime("%H:%M:%S", time.localtime(current_time))
                    node_short = node_id[-4:] if len(node_id) >= 4 else node_id
                    
                    # Update the lastHeard timestamp in the interface's nodes dict
                    if hasattr(interface, 'nodes') and node_id in interface.nodes:
                        interface.nodes[node_id]['lastHeard'] = current_time
                        print(f"DEBUG [{timestamp}] Updated lastHeard for node ...{node_short} from {packet_type} packet")
                        
            except Exception as e:
                # Don't let packet processing errors break the callback
                timestamp = time.strftime("%H:%M:%S", time.localtime())
                print(f"Warning [{timestamp}]: Error processing {packet_type} packet: {e}")
        
        def on_packet_received(packet, interface):  # pylint: disable=unused-argument
            """Callback function called when a general packet is received."""
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            print(f"DEBUG [{timestamp}]: on_packet_received called - packet type: {type(packet)}")
            if packet:
                print(f"DEBUG [{timestamp}]: packet keys: {list(packet.keys()) if hasattr(packet, 'keys') else 'no keys'}")
            update_last_heard(packet, interface, "general")
        
        def on_telemetry_received(packet, interface):  # pylint: disable=unused-argument
            """Callback function called when telemetry data is received."""
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            print(f"DEBUG [{timestamp}]: on_telemetry_received called - packet type: {type(packet)}")
            if packet:
                print(f"DEBUG [{timestamp}]: packet keys: {list(packet.keys()) if hasattr(packet, 'keys') else 'no keys'}")
            update_last_heard(packet, interface, "telemetry")
        
        # Set up callbacks for different packet types
        self.setup_callbacks(
            on_receive=on_packet_received,
            on_telemetry=on_telemetry_received
        )
        
        # Add a general listener to see what events are being published
        if pub:
            def debug_listener(message, topic=pub.AUTO_TOPIC):
                timestamp = time.strftime("%H:%M:%S", time.localtime())
                print(f"DEBUG [{timestamp}]: PubSub event received - topic: {topic}")
            
            # Subscribe to all meshtastic events
            pub.subscribe(debug_listener, "meshtastic")
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            print(f"DEBUG [{timestamp}]: Added general meshtastic event listener")
        
        # Also try to set up additional hooks that might exist
        try:
            # Try to hook into the interface's internal telemetry handler
            if hasattr(self.interface, '_onTelemetryReceive'):
                original_handler = self.interface._onTelemetryReceive
                def enhanced_telemetry_handler(packet, interface):
                    # Call the original handler first
                    original_handler(packet, interface)
                    # Then update our lastHeard timestamp
                    update_last_heard(packet, interface, "telemetry_handler")
                self.interface._onTelemetryReceive = enhanced_telemetry_handler
                timestamp = time.strftime("%H:%M:%S", time.localtime())
                print(f"DEBUG [{timestamp}]: Enhanced telemetry handler installed")
        except Exception as e:
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            print(f"DEBUG [{timestamp}]: Could not enhance telemetry handler: {e}")
    
    def setup_comprehensive_hooks(self) -> None:
        """
        Set up comprehensive hooks to catch all types of packets.
        This method tries multiple approaches to ensure we catch telemetry and other packet types.
        """
        if not self.interface:
            return
            
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        print(f"DEBUG [{timestamp}]: Setting up comprehensive packet hooks...")
        
        # List all available methods on the interface
        interface_methods = [method for method in dir(self.interface) if not method.startswith('__')]
        print(f"DEBUG [{timestamp}]: Available interface methods: {interface_methods}")
        
        # Check for specific attributes that might contain packet data
        if hasattr(self.interface, 'packets'):
            print(f"DEBUG [{timestamp}]: Interface has 'packets' attribute")
        if hasattr(self.interface, 'recent_packets'):
            print(f"DEBUG [{timestamp}]: Interface has 'recent_packets' attribute")
        if hasattr(self.interface, '_packets'):
            print(f"DEBUG [{timestamp}]: Interface has '_packets' attribute")
        
        # Try to find and hook telemetry-related methods
        telemetry_methods = [method for method in interface_methods if 'telemetry' in method.lower()]
        print(f"DEBUG [{timestamp}]: Telemetry-related methods: {telemetry_methods}")
        
        # Also look for packet-related methods
        packet_methods = [method for method in interface_methods if 'packet' in method.lower()]
        print(f"DEBUG [{timestamp}]: Packet-related methods: {packet_methods}")
        
        # Look for receive-related methods
        receive_methods = [method for method in interface_methods if 'receive' in method.lower()]
        print(f"DEBUG [{timestamp}]: Receive-related methods: {receive_methods}")
        
        # Try to hook into any telemetry methods we find
        for method_name in telemetry_methods:
            try:
                original_method = getattr(self.interface, method_name)
                if callable(original_method):
                    def create_enhanced_handler(orig_method, name):
                        def enhanced_handler(*args, **kwargs):
                            result = orig_method(*args, **kwargs)
                            # Try to extract node info from args/kwargs
                            if args and len(args) > 0:
                                packet = args[0] if args else None
                                if packet and hasattr(packet, 'from_id'):
                                    node_id = packet.from_id
                                    current_time = int(time.time())
                                    timestamp = time.strftime("%H:%M:%S", time.localtime(current_time))
                                    node_short = node_id[-4:] if len(node_id) >= 4 else node_id
                                    if hasattr(self.interface, 'nodes') and node_id in self.interface.nodes:
                                        self.interface.nodes[node_id]['lastHeard'] = current_time
                                        print(f"DEBUG [{timestamp}] Updated lastHeard for node ...{node_short} from {name}")
                            return result
                        return enhanced_handler
                    
                    setattr(self.interface, method_name, create_enhanced_handler(original_method, method_name))
                    timestamp = time.strftime("%H:%M:%S", time.localtime())
                    print(f"DEBUG [{timestamp}]: Enhanced {method_name} method")
            except Exception as e:
                timestamp = time.strftime("%H:%M:%S", time.localtime())
                print(f"DEBUG [{timestamp}]: Could not enhance {method_name}: {e}")
    
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
    

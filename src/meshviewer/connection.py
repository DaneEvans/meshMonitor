"""
Meshtastic connection management module.
"""
import meshtastic
import meshtastic.tcp_interface
import meshtastic.serial_interface
from pubsub import pub
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
            if port:
                self.interface = serial_interface.SerialInterface(port)
            else:
                self.interface = serial_interface.SerialInterface()
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
                       on_connection: Optional[Callable] = None) -> None:
        """
        Setup callback functions for packet reception and connection events.
        
        Args:
            on_receive: Function to call when a packet is received
            on_connection: Function to call when connection is established
        """
        if on_receive:
            pub.subscribe(on_receive, "meshtastic.receive")
        if on_connection:
            pub.subscribe(on_connection, "meshtastic.connection.established")
    
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

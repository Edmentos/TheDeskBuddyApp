import serial
import serial.tools.list_ports
from typing import Optional, List, Dict
import json
import time
import threading


class ESP32SerialReader:
    """Manages serial connection to ESP32 device"""
    
    def __init__(self):
        self.serial_connection: Optional[serial.Serial] = None
        self.port: Optional[str] = None
        self.is_connected: bool = False
        self.latest_data: Optional[Dict] = None
        self.read_thread: Optional[threading.Thread] = None
        self.stop_reading: bool = False
    
    @staticmethod
    def list_available_ports() -> List[Dict[str, str]]:
        """List all available serial ports"""
        ports = []
        for port in serial.tools.list_ports.comports():
            ports.append({
                "port": port.device,
                "description": port.description,
                "hwid": port.hwid
            })
        return ports
    
    def connect(self, port: str, baudrate: int = 115200, timeout: float = 2.0) -> bool:
        """
        Connect to ESP32 on specified port
        
        Common issues and solutions:
        - Baudrate must match ESP32 configuration (default 115200)
        - Timeout should be reasonable (1-3 seconds)
        - Port might need permissions on Linux (add user to dialout group)
        """
        if self.is_connected:
            return True
        
        try:
            # Create serial connection with proper settings
            self.serial_connection = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=timeout,
                write_timeout=timeout
            )
            
            # Give the connection a moment to stabilize
            time.sleep(0.5)
            
            # Clear any stale data in buffers
            self.serial_connection.reset_input_buffer()
            self.serial_connection.reset_output_buffer()
            
            self.port = port
            self.is_connected = True
            self.stop_reading = False
            
            # Start background thread to read data
            self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.read_thread.start()
            
            return True
            
        except serial.SerialException as e:
            print(f"Failed to connect to {port}: {e}")
            self.is_connected = False
            return False
        except Exception as e:
            print(f"Unexpected error connecting to {port}: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self):
        """Disconnect from ESP32"""
        self.stop_reading = True
        self.is_connected = False
        
        if self.read_thread:
            self.read_thread.join(timeout=2.0)
        
        if self.serial_connection and self.serial_connection.is_open:
            try:
                self.serial_connection.close()
            except Exception as e:
                print(f"Error closing serial connection: {e}")
        
        self.serial_connection = None
        self.port = None
        self.latest_data = None
    
    def _read_loop(self):
        """Background thread to continuously read from serial port"""
        while not self.stop_reading and self.serial_connection and self.serial_connection.is_open:
            try:
                if self.serial_connection.in_waiting > 0:
                    line = self.serial_connection.readline()
                    try:
                        # Decode and strip whitespace
                        data_str = line.decode('utf-8').strip()
                        
                        # Try to parse as JSON
                        try:
                            data = json.loads(data_str)
                            self.latest_data = data
                        except json.JSONDecodeError:
                            # If not JSON, store as raw string
                            self.latest_data = {"raw": data_str}
                    except UnicodeDecodeError:
                        # If decoding fails, store as raw bytes
                        self.latest_data = {"raw_bytes": line.hex()}
                
                time.sleep(0.01)  # Small delay to prevent CPU spinning
                
            except serial.SerialException as e:
                print(f"Serial read error: {e}")
                self.is_connected = False
                break
            except Exception as e:
                print(f"Unexpected error in read loop: {e}")
                time.sleep(0.1)
    
    def get_latest_data(self) -> Optional[Dict]:
        """Get the most recent data received from ESP32"""
        return self.latest_data
    
    def get_status(self) -> Dict:
        """Get current connection status"""
        return {
            "connected": self.is_connected,
            "port": self.port,
            "has_data": self.latest_data is not None
        }


# Global instance
esp32_reader = ESP32SerialReader()

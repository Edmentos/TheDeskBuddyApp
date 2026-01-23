# reads data from ESP32 over serial
import json
import re
import threading
import time
from typing import Callable, Dict, List, Optional

import serial
import serial.tools.list_ports


class ESP32SerialReader:
    # handles serial stuff for ESP32
    def __init__(self, on_reading: Optional[Callable[[Dict], None]] = None):
        self.serial_connection: Optional[serial.Serial] = None
        self.port: Optional[str] = None
        self.is_connected: bool = False
        self.latest_data: Optional[Dict] = None
        self.read_thread: Optional[threading.Thread] = None
        self.stop_reading: bool = False
        self.on_reading = on_reading
        self.auto_reconnect = False

    @staticmethod
    def list_available_ports() -> List[Dict[str, str]]:
        return [
            {"port": p.device, "description": p.description, "hwid": p.hwid}
            for p in serial.tools.list_ports.comports()
        ]

    @staticmethod
    def find_esp32_port() -> Optional[str]:
        # tries to find ESP32 automatically
        esp32_identifiers = [
            'CP210', 'CH340', 'CH341', 'UART', 'USB-SERIAL', 'USB2.0-Serial'
        ]

        for port in serial.tools.list_ports.comports():
            description = port.description.upper()
            hwid = port.hwid.upper()

            if any(
                identifier in description or identifier in hwid
                for identifier in esp32_identifiers
            ):
                return port.device
        return None

    def auto_connect(self, baudrate: int = 115200) -> bool:
        # auto find and connect
        esp32_port = self.find_esp32_port()
        if esp32_port:
            return self.connect(esp32_port, baudrate)
        return False

    def connect(
        self,
        port: str,
        baudrate: int = 115200,
        timeout: float = 2.0,
        auto_reconnect: bool = True
    ) -> bool:
        if self.is_connected:
            return True

        try:
            self.serial_connection = serial.Serial(
                port=port, baudrate=baudrate, timeout=timeout, write_timeout=timeout,
                xonxoff=False, rtscts=False, dsrdtr=False
            )
            time.sleep(1.0)
            self.serial_connection.reset_input_buffer()
            self.serial_connection.reset_output_buffer()

            self.port = port
            self.is_connected = True
            self.auto_reconnect = auto_reconnect
            self.stop_reading = False
            self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.read_thread.start()
            return True

        except (serial.SerialException, OSError) as e:
            print(f"Connection error: {e}")
            self.is_connected = False
            return False

    def disconnect(self):
        self.stop_reading = True
        self.is_connected = False

        if self.read_thread:
            self.read_thread.join(timeout=2.0)

        if self.serial_connection and self.serial_connection.is_open:
            try:
                self.serial_connection.close()
            except (serial.SerialException, OSError) as e:
                print(f"Close error: {e}")

        self.serial_connection = None
        self.port = None
        self.latest_data = None

    def _read_loop(self):
        # background thread that reads from serial port
        while not self.stop_reading:
            if not self.serial_connection or not self.serial_connection.is_open:
                if self.auto_reconnect and self.port:
                    print(f"Attempting to reconnect to {self.port}...")
                    time.sleep(2.0)
                    try:
                        self.serial_connection = serial.Serial(
                            port=self.port, baudrate=115200, timeout=2.0,
                            xonxoff=False, rtscts=False, dsrdtr=False
                        )
                        self.is_connected = True
                        print(f"Reconnected to {self.port}")
                    except (serial.SerialException, OSError):
                        continue
                else:
                    break

            try:
                if self.serial_connection.in_waiting > 0:
                    line = self.serial_connection.readline()
                    try:
                        data_str = line.decode('utf-8').strip()
                        # Strip Arduino Serial Monitor timestamp
                        # (e.g., "17:09:47.625 -> ")
                        data_str = re.sub(
                            r'^\d{2}:\d{2}:\d{2}\.\d{3}\s*->\s*',
                            '',
                            data_str
                        )

                        if not data_str:
                            continue

                        try:
                            data = json.loads(data_str)
                            self.latest_data = data
                            if self.on_reading:
                                self.on_reading(data)
                        except json.JSONDecodeError:
                            self.latest_data = {"raw": data_str}
                    except UnicodeDecodeError:
                        self.latest_data = {"raw_bytes": line.hex()}
                time.sleep(0.01)
            except serial.SerialException:
                print("Serial connection lost")
                self.is_connected = False
                if not self.auto_reconnect:
                    break
            except (UnicodeDecodeError, json.JSONDecodeError, OSError) as e:
                print(f"Read error: {e}")
                time.sleep(0.1)

    def get_latest_data(self) -> Optional[Dict]:
        return self.latest_data

    def get_status(self) -> Dict:
        return {
            "connected": self.is_connected,
            "port": self.port,
            "has_data": self.latest_data is not None
        }


esp32_reader = ESP32SerialReader()

import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Callable
import serial
import serial.tools.list_ports
from app.db.db import SessionLocal
from app.db.models import Reading

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def detect_port() -> Optional[str]:
    """Auto-detect ESP32 serial port (CP210x/CH340/ESP32)"""
    keywords = ['CP210', 'CH340', 'ESP32', 'UART', 'USB-SERIAL']
    for port in serial.tools.list_ports.comports():
        port_info = f"{port.device} {port.description} {port.hwid}".upper()
        if any(kw in port_info for kw in keywords):
            logger.info(f"Detected ESP32: {port.device}")
            return port.device
    return None


def parse_line_to_reading(line: str) -> Optional[Dict[str, Any]]:
    """Parse serial line with optional prefix, extract JSON from first '{'"""
    try:
        line = line.strip()
        json_start = line.find('{')
        if json_start == -1:
            return None
        
        payload = json.loads(line[json_start:])
        if not all(k in payload for k in ['ts_ms', 'distance_cm', 'temp_c', 'hum_pct']):
            return None
        
        return {
            'ts_utc': datetime.now(timezone.utc).isoformat(),
            'device_ts_ms': payload['ts_ms'],
            'distance_cm': float(payload['distance_cm']),
            'temp_c': float(payload['temp_c']),
            'hum_pct': float(payload['hum_pct'])
        }
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.warning(f"Parse error: {e}")
        return None


def read_loop(on_reading: Optional[Callable] = None, port: Optional[str] = None, 
              baud_rate: int = 115200, reconnect_delay: float = 2.0) -> None:
    """Read loop with auto-reconnect, parse JSON, persist to DB"""
    logger.info("Starting serial reader...")
    
    while True:
        ser = None
        try:
            port_to_use = port or detect_port()
            if not port_to_use:
                logger.warning(f"No device found, retry in {reconnect_delay}s")
                time.sleep(reconnect_delay)
                continue
            
            ser = serial.Serial(port_to_use, baud_rate, timeout=1.0)
            logger.info(f"Connected to {port_to_use}")
            
            while ser.is_open:
                line = ser.readline().decode('utf-8', errors='ignore')
                reading = parse_line_to_reading(line)
                
                if reading:
                    logger.info(f"{reading['distance_cm']:.1f}cm | "
                              f"{reading['temp_c']:.1f}°C | {reading['hum_pct']:.0f}%")
                    
                    db = SessionLocal()
                    try:
                        ts = datetime.fromisoformat(reading['ts_utc'].replace('Z', '+00:00'))
                        db.add_all([
                            Reading(ts=ts, sensor='distance', value=reading['distance_cm'], unit='cm'),
                            Reading(ts=ts, sensor='temperature', value=reading['temp_c'], unit='celsius'),
                            Reading(ts=ts, sensor='humidity', value=reading['hum_pct'], unit='percent')
                        ])
                        db.commit()
                    except Exception as e:
                        logger.error(f"DB error: {e}")
                        db.rollback()
                    finally:
                        db.close()
                    
                    if on_reading:
                        on_reading(reading)
                        
        except (serial.SerialException, Exception) as e:
            logger.error(f"Connection error: {e}")
        finally:
            if ser and ser.is_open:
                ser.close()
            port = None
            logger.info(f"Reconnecting in {reconnect_delay}s...")
            time.sleep(reconnect_delay)


def start_reader_thread():
    """Start reader in background thread"""
    import threading
    thread = threading.Thread(target=read_loop, daemon=True)
    thread.start()
    return thread


if __name__ == "__main__":
    read_loop()

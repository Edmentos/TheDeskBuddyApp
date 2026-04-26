"""
NOT IN USE - this is the old serial reader from before the refactor.

The live implementation is at app/serial/serial_reader.py, which is what main.py imports.
This file writes wrong sensor names to the DB ('distance', 'temperature', 'humidity')
instead of the ones the frontend queries ('distance_cm', 'temp_c', 'hum_pct'), so
do NOT run this directly or re-import it.
"""
import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Callable
import serial
import serial.tools.list_ports
from app.db.db import SessionLocal
from app.db.models import Reading
from app.posture import get_posture_tracker
from app.posture_events import get_event_logger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def detect_port() -> Optional[str]:
    """Auto-detect ESP32 serial port (CP210x/CH340/ESP32)"""
    keywords = ['CP210', 'CH340', 'ESP32', 'UART', 'USB-SERIAL']
    for port in serial.tools.list_ports.comports():
        port_info = f"{port.device} {port.description} {port.hwid}".upper()
        if any(kw in port_info for kw in keywords):
            logger.info("Detected ESP32: %s", port.device)
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
        required_keys = ['ts_ms', 'distance_cm', 'temp_c', 'hum_pct']
        if not all(k in payload for k in required_keys):
            return None

        return {
            'ts_utc': datetime.now(timezone.utc).isoformat(),
            'device_ts_ms': payload['ts_ms'],
            'distance_cm': float(payload['distance_cm']),
            'temp_c': float(payload['temp_c']),
            'hum_pct': float(payload['hum_pct'])
        }
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.warning("Parse error: %s", e)
        return None


def read_loop(
        on_reading: Optional[Callable] = None,
        port: Optional[str] = None,
        baud_rate: int = 115200,
        reconnect_delay: float = 2.0) -> None:
    """Read loop with auto-reconnect, parse JSON, persist to DB"""
    logger.info("Starting serial reader...")

    # setup posture tracker with event logging
    event_logger = get_event_logger()
    tracker = get_posture_tracker(on_state_change=event_logger.on_state_change)

    while True:
        ser = None
        try:
            port_to_use = port or detect_port()
            if not port_to_use:
                logger.warning(
                    "No device found, retry in %ss", reconnect_delay
                )
                time.sleep(reconnect_delay)
                continue

            ser = serial.Serial(port_to_use, baud_rate, timeout=1.0)
            logger.info("Connected to %s", port_to_use)

            while ser.is_open:
                line = ser.readline().decode('utf-8', errors='ignore')
                reading = parse_line_to_reading(line)

                if reading:
                    # check posture from distance
                    tracker = get_posture_tracker()
                    posture = tracker.process_distance(reading['distance_cm'])
                    smoothed_distance = tracker.get_smoothed_distance()

                    logger.info(
                        "%scm (smoothed: %.1fcm) | %s | %s°C | %s%%",
                        f"{reading['distance_cm']:.1f}",
                        smoothed_distance,
                        posture,
                        f"{reading['temp_c']:.1f}",
                        f"{reading['hum_pct']:.0f}"
                    )

                    db = SessionLocal()
                    try:
                        ts_str = reading['ts_utc'].replace('Z', '+00:00')
                        ts = datetime.fromisoformat(ts_str)
                        db.add_all([
                            Reading(
                                ts=ts,
                                sensor='distance',
                                value=reading['distance_cm'],
                                unit='cm'
                            ),
                            Reading(
                                ts=ts,
                                sensor='temperature',
                                value=reading['temp_c'],
                                unit='celsius'
                            ),
                            Reading(
                                ts=ts,
                                sensor='humidity',
                                value=reading['hum_pct'],
                                unit='percent'
                            ),
                            Reading(
                                ts=ts,
                                sensor='posture',
                                value=1.0 if posture == 'standing' else 0.0,
                                unit=posture
                            )
                        ])
                        db.commit()
                    except (ValueError, KeyError) as e:
                        logger.error("DB error: %s", e)
                        db.rollback()
                    finally:
                        db.close()

                    if on_reading:
                        on_reading(reading)

        except serial.SerialException as e:
            logger.error("Connection error: %s", e)
        finally:
            if ser and ser.is_open:
                ser.close()
            port = None
            logger.info("Reconnecting in %ss...", reconnect_delay)
            time.sleep(reconnect_delay)


def start_reader_thread():
    """Start reader in background thread"""
    thread = threading.Thread(target=read_loop, daemon=True)
    thread.start()
    return thread


if __name__ == "__main__":
    read_loop()

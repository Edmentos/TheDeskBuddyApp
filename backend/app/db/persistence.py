"""save readings from ESP32 and audio worker to postgres"""
import logging
from datetime import datetime, timezone
from typing import Dict

from sqlalchemy.exc import SQLAlchemyError

from app.db.db import SessionLocal
from app.db.models import Reading

logger = logging.getLogger(__name__)


def save_reading_to_db(data: Dict):
    """save sensor reading to database"""
    # write sensor data to db
    db = SessionLocal()
    try:
        ts = datetime.now(timezone.utc)
        device_ts_ms = data.get("ts_ms")

        sensors = {
            "temp_c": ("°C", data.get("temp_c")),
            "hum_pct": ("%", data.get("hum_pct")),
            "distance_cm": ("cm", data.get("distance_cm"))
        }

        for sensor_name, (unit, value) in sensors.items():
            if value is not None:
                reading = Reading(
                    ts=ts,
                    sensor=sensor_name,
                    value=float(value),
                    unit=unit,
                    device_ts_ms=device_ts_ms
                )
                db.add(reading)

        db.commit()
    except (SQLAlchemyError, ValueError) as e:
        logger.error("Failed to save sensor reading: %s", e)
        db.rollback()
    finally:
        db.close()


def save_noise_reading_to_db(smoothed_db: float):
    """save noise reading from audio worker to database"""
    db = SessionLocal()
    try:
        ts = datetime.now(timezone.utc)

        # Store smoothed dB as the main value (less noisy)
        reading = Reading(
            ts=ts,
            sensor="noise_db",
            value=float(smoothed_db),
            unit="dB",
            device_ts_ms=None  # audio readings are local, no device timestamp
        )
        db.add(reading)
        db.commit()
    except (SQLAlchemyError, ValueError) as e:
        logger.error("Failed to save noise reading: %s", e)
        db.rollback()
    finally:
        db.close()

# saves sensor data to postgres
from datetime import datetime, timezone
from typing import Dict

from sqlalchemy.exc import SQLAlchemyError

from app.db.db import SessionLocal
from app.db.models import Reading


def save_reading_to_db(data: Dict):
    # saves reading to db
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
        print(f"Database error: {e}")
        db.rollback()
    finally:
        db.close()

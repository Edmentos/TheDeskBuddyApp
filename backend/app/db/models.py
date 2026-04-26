"""SQLAlchemy models for the readings table"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Index, Boolean
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Reading(Base):
    """table for storing sensor data"""
    __tablename__ = "readings"

    id = Column(Integer, primary_key=True, index=True)
    ts = Column(DateTime, nullable=False, index=True)
    sensor = Column(String, nullable=False, index=True)
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=True)
    device_ts_ms = Column(Integer, nullable=True)

    __table_args__ = (
        # index for time + sensor queries
        Index('ix_readings_ts_sensor', 'ts', 'sensor'),
        # sensor first, then time (better for our queries)
        Index('ix_readings_sensor_ts', 'sensor', 'ts'),
        # desc order index for newest-first queries
        Index('ix_readings_sensor_ts_desc', 'sensor', ts.desc()),
    )


class Calibration(Base):
    """stores user's desk height calibration"""
    __tablename__ = "calibration"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, nullable=False, index=True)
    sitting_height_cm = Column(Float, nullable=False)
    standing_height_cm = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)


class PostureEvent(Base):
    """tracks sitting/standing transitions and durations"""
    __tablename__ = "posture_events"

    id = Column(Integer, primary_key=True, index=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    posture = Column(String, nullable=False)  # 'sitting' or 'standing'
    duration_seconds = Column(Float, nullable=True)

    __table_args__ = (
        Index('ix_posture_events_start_time', 'start_time'),
        Index('ix_posture_events_posture_start', 'posture', 'start_time'),
    )

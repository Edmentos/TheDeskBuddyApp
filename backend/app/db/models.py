"""Database models for sensor readings."""
from sqlalchemy import Column, Integer, String, Float, DateTime, Index
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Reading(Base):
    """Sensor reading model"""
    __tablename__ = "readings"

    id = Column(Integer, primary_key=True, index=True)
    ts = Column(DateTime, nullable=False, index=True)
    sensor = Column(String, nullable=False, index=True)
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=True)
    device_ts_ms = Column(Integer, nullable=True)

    __table_args__ = (
        Index('ix_readings_ts_sensor', 'ts', 'sensor'),
    )

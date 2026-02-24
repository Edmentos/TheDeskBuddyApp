"""settings endpoints for configuring posture detection"""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.posture import get_posture_tracker
from app.db.db import get_db
from app.db.models import Calibration
from app.serial.serial_reader import esp32_reader

router = APIRouter(prefix="/settings", tags=["settings"])


class PostureSettings(BaseModel):
    """user settings for posture thresholds"""
    sitting_height_cm: float = Field(..., gt=0, le=200)
    standing_offset_cm: float = Field(default=10.0, gt=0, le=50)


@router.get("/posture")
async def get_posture_settings():
    """get current posture settings"""
    tracker = get_posture_tracker()
    config = tracker.get_config()
    return {
        "sitting_height_cm": config["sitting_height_cm"],
        "standing_offset_cm": config["standing_offset_cm"],
        "standing_threshold_cm": config["standing_threshold_cm"],
        "current_state": tracker.current_state,
        "smoothed_distance_cm": tracker.get_smoothed_distance()
    }


@router.put("/posture")
async def update_posture_settings(settings: PostureSettings):
    """update posture settings from frontend"""
    tracker = get_posture_tracker()
    tracker.update_thresholds(
        sitting_height_cm=settings.sitting_height_cm,
        standing_offset_cm=settings.standing_offset_cm
    )

    config = tracker.get_config()
    return {
        "status": "updated",
        "sitting_height_cm": config["sitting_height_cm"],
        "standing_offset_cm": config["standing_offset_cm"],
        "standing_threshold_cm": config["standing_threshold_cm"]
    }


@router.post("/calibrate/record-sitting")
async def record_sitting_height():
    """capture current distance as sitting height"""
    # get latest distance reading
    data = esp32_reader.get_latest_data()
    if not data or 'distance_cm' not in data:
        raise HTTPException(status_code=400, detail="No sensor data available")

    distance = data['distance_cm']
    if distance <= 0 or distance > 200:
        raise HTTPException(status_code=400, detail="Invalid distance reading")

    return {
        "sitting_height_cm": distance,
        "message": "Sitting height recorded"
    }


@router.post("/calibrate/record-standing")
async def record_standing_height():
    """capture current distance as standing height"""
    data = esp32_reader.get_latest_data()
    if not data or 'distance_cm' not in data:
        raise HTTPException(status_code=400, detail="No sensor data available")

    distance = data['distance_cm']
    if distance <= 0 or distance > 200:
        raise HTTPException(status_code=400, detail="Invalid distance reading")

    return {
        "standing_height_cm": distance,
        "message": "Standing height recorded"
    }


class CalibrationData(BaseModel):
    """calibration heights"""
    sitting_height_cm: float = Field(..., gt=0, le=200)
    standing_height_cm: float = Field(..., gt=0, le=200)


@router.post("/calibrate/save")
async def save_calibration(cal: CalibrationData, db: Session = Depends(get_db)):
    """save calibration to database"""
    if cal.sitting_height_cm >= cal.standing_height_cm:
        raise HTTPException(
            status_code=400,
            detail="Standing height must be greater than sitting height"
        )

    # deactivate old calibrations
    db.query(Calibration).update({"is_active": False})

    # save new calibration
    new_cal = Calibration(
        created_at=datetime.now(timezone.utc),
        sitting_height_cm=cal.sitting_height_cm,
        standing_height_cm=cal.standing_height_cm,
        is_active=True
    )
    db.add(new_cal)
    db.commit()

    # update posture tracker with midpoint as threshold
    midpoint = (cal.sitting_height_cm + cal.standing_height_cm) / 2
    offset = cal.standing_height_cm - midpoint

    tracker = get_posture_tracker()
    tracker.update_thresholds(
        sitting_height_cm=midpoint,
        standing_offset_cm=offset
    )

    return {
        "status": "calibrated",
        "sitting_height_cm": cal.sitting_height_cm,
        "standing_height_cm": cal.standing_height_cm,
        "threshold": midpoint
    }


@router.get("/calibrate/current")
async def get_current_calibration(db: Session = Depends(get_db)):
    """get active calibration"""
    cal = db.query(Calibration).filter(
        Calibration.is_active.is_(True)
    ).order_by(Calibration.created_at.desc()).first()

    if not cal:
        return {"calibrated": False}

    return {
        "calibrated": True,
        "sitting_height_cm": cal.sitting_height_cm,
        "standing_height_cm": cal.standing_height_cm,
        "created_at": cal.created_at.isoformat()
    }


# In-memory storage for noise thresholds (simple approach)
_noise_thresholds = {
    "quiet": 50.0,    # Below this = quiet
    "normal": 60.0,   # Below this = normal
    "loud": 70.0      # Above this = loud, else moderate
}


class NoiseThresholds(BaseModel):
    """Noise level thresholds in dB."""
    quiet: Optional[float] = Field(50.0, ge=30, le=120)
    normal: Optional[float] = Field(60.0, ge=30, le=120)
    loud: Optional[float] = Field(70.0, ge=30, le=120)


@router.get("/noise-thresholds")
async def get_noise_thresholds():
    """Get current noise threshold settings."""
    return _noise_thresholds


@router.put("/noise-thresholds")
async def update_noise_thresholds(thresholds: NoiseThresholds):
    """Update noise threshold settings."""
    if thresholds.quiet:
        _noise_thresholds["quiet"] = thresholds.quiet
    if thresholds.normal:
        _noise_thresholds["normal"] = thresholds.normal
    if thresholds.loud:
        _noise_thresholds["loud"] = thresholds.loud

    return {"status": "updated", **_noise_thresholds}

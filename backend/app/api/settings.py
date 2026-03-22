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
from app.webcam_runtime import get_active_webcam_worker

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


class WebcamToleranceSettings(BaseModel):
    """Tolerance values used against webcam baseline features."""
    head_forward: float = Field(0.08, ge=0.0, le=1.0)
    neck_angle_norm: float = Field(0.12, ge=0.0, le=1.0)
    shoulder_alignment: float = Field(0.06, ge=0.0, le=1.0)


class WebcamCalibrationRequest(BaseModel):
    """Calibration request for webcam posture baseline."""
    duration_sec: float = Field(6.0, ge=2.0, le=20.0)
    min_samples: int = Field(6, ge=3, le=60)


@router.get("/webcam/posture")
async def get_webcam_posture_settings():
    """Get webcam baseline + tolerance settings."""
    worker = get_active_webcam_worker()
    if not worker:
        return {
            "webcam_available": False,
            "running": False,
            "baseline": None,
            "tolerances": None
        }

    running = worker.is_running()

    return {
        "webcam_available": running,
        "running": running,
        "baseline": worker.get_baseline(),
        "tolerances": worker.get_tolerances()
    }


@router.put("/webcam/posture")
async def update_webcam_posture_settings(settings: WebcamToleranceSettings):
    """Update webcam baseline tolerance settings."""
    worker = get_active_webcam_worker()
    if not worker or not worker.is_running():
        raise HTTPException(status_code=503, detail="Webcam worker is not running")

    worker.update_tolerances(
        head_forward=settings.head_forward,
        neck_angle_norm=settings.neck_angle_norm,
        shoulder_alignment=settings.shoulder_alignment
    )

    return {
        "status": "updated",
        "tolerances": worker.get_tolerances(),
        "baseline": worker.get_baseline()
    }


@router.post("/webcam/calibrate")
async def calibrate_webcam_posture(req: WebcamCalibrationRequest):
    """Capture a short good-posture baseline from webcam landmarks."""
    worker = get_active_webcam_worker()
    if not worker or not worker.is_running():
        raise HTTPException(status_code=503, detail="Webcam worker is not running")

    try:
        baseline = worker.calibrate_baseline(
            duration_sec=req.duration_sec,
            min_samples=req.min_samples
        )
        return {
            "status": "calibrated",
            "baseline": baseline,
            "tolerances": worker.get_tolerances()
        }
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/webcam/worker/stop")
async def stop_webcam_worker():
    """Temporarily stop webcam worker (useful if browser preview needs camera)."""
    worker = get_active_webcam_worker()
    if not worker:
        return {"status": "ok", "running": False}

    if worker.is_running():
        worker.stop()
    return {"status": "ok", "running": False}


@router.post("/webcam/worker/start")
async def start_webcam_worker():
    """Start webcam worker again after temporary pause."""
    worker = get_active_webcam_worker()
    if not worker:
        raise HTTPException(status_code=503, detail="Webcam worker is not initialized")

    if not worker.is_running():
        worker.start()
    return {"status": "ok", "running": True}

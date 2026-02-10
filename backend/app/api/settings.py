"""settings endpoints for configuring posture detection"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.posture import get_posture_tracker

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

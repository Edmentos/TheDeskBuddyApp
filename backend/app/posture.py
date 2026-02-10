"""handles posture detection based on desk height"""
from collections import deque
from typing import Literal

PostureState = Literal["sitting", "standing"]


class PostureTracker:
    """tracks if user is sitting or standing based on desk height"""

    def __init__(self, sitting_height_cm: float = 80.0, standing_offset_cm: float = 10.0):
        """setup the tracker with user's desk height settings"""
        self.sitting_height_cm = sitting_height_cm
        self.standing_offset_cm = standing_offset_cm
        self.standing_threshold_cm = sitting_height_cm + standing_offset_cm

        # keep last 5 readings to smooth out sensor noise
        self.distance_buffer: deque = deque(maxlen=5)
        self.current_state: PostureState = "sitting"

    def update_thresholds(self, sitting_height_cm: float, standing_offset_cm: float = 10.0):
        """update when user changes settings"""
        self.sitting_height_cm = sitting_height_cm
        self.standing_offset_cm = standing_offset_cm
        self.standing_threshold_cm = sitting_height_cm + standing_offset_cm

    def process_distance(self, distance_cm: float) -> PostureState:
        """figure out if sitting or standing from distance reading"""
        # ignore bad readings from sensor
        if distance_cm is None or not isinstance(distance_cm, (int, float)):
            return self.current_state

        if distance_cm < 0 or distance_cm > 400:  # sensor acts weird sometimes
            return self.current_state

        self.distance_buffer.append(distance_cm)

        # calculate average of last few readings
        if len(self.distance_buffer) > 0:
            smoothed = sum(self.distance_buffer) / len(self.distance_buffer)
        else:
            smoothed = distance_cm

        # check if standing or sitting
        if smoothed >= self.standing_threshold_cm:
            self.current_state = "standing"
        else:
            self.current_state = "sitting"

        return self.current_state

    def get_smoothed_distance(self) -> float:
        """get averaged distance value"""
        if len(self.distance_buffer) > 0:
            return sum(self.distance_buffer) / len(self.distance_buffer)
        return 0.0

    def get_config(self) -> dict:
        """return current settings"""
        return {
            "sitting_height_cm": self.sitting_height_cm,
            "standing_offset_cm": self.standing_offset_cm,
            "standing_threshold_cm": self.standing_threshold_cm
        }


# singleton pattern - only one tracker for the whole app
_posture_tracker: PostureTracker | None = None


def get_posture_tracker() -> PostureTracker:
    """get the global tracker instance"""
    global _posture_tracker
    if _posture_tracker is None:
        _posture_tracker = PostureTracker()
    return _posture_tracker

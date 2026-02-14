"""handles posture detection based on desk height"""
import time
from collections import deque
from typing import Literal, Optional, Callable
from datetime import datetime, timezone

PostureState = Literal["sitting", "standing"]


class PostureTracker:
    """tracks if user is sitting or standing based on desk height"""

    def __init__(
        self,
        sitting_height_cm: float = 80.0,
        standing_offset_cm: float = 10.0,
        on_state_change: Optional[
            Callable[[PostureState, PostureState, datetime], None]
        ] = None
    ):
        """setup the tracker with user's desk height settings"""
        self.sitting_height_cm = sitting_height_cm
        self.standing_offset_cm = standing_offset_cm
        self.standing_threshold_cm = sitting_height_cm + standing_offset_cm

        # hysteresis - prevents flickering at boundaries
        self.hysteresis_cm = 5.0  # add some buffer zone

        # minimum time in new state before confirming (prevents quick bounces)
        self.min_duration_sec = 3.0

        # keep last 5 readings to smooth out sensor noise
        self.distance_buffer: deque = deque(maxlen=5)
        self.current_state: PostureState = "sitting"

        # track potential state change
        self.candidate_state: Optional[PostureState] = None
        self.candidate_start_time: Optional[float] = None
        self.last_state_change: Optional[datetime] = None

        # callback for when state actually changes
        self.on_state_change = on_state_change

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

        # figure out what state the distance indicates using hysteresis
        new_state = self._check_state_with_hysteresis(smoothed)

        # update state machine with duration check
        self._update_state(new_state)

        return self.current_state

    def _check_state_with_hysteresis(self, smoothed_distance: float) -> PostureState:
        """check state using hysteresis to prevent bouncing"""
        # different thresholds depending on current state
        if self.current_state == "sitting":
            # need to go higher to switch to standing
            if smoothed_distance >= (self.standing_threshold_cm + self.hysteresis_cm):
                return "standing"
            else:
                return "sitting"
        else:  # currently standing
            # need to go lower to switch to sitting
            if smoothed_distance <= (self.standing_threshold_cm - self.hysteresis_cm):
                return "sitting"
            else:
                return "standing"

    def _update_state(self, new_state: PostureState):
        """update state with minimum duration check"""
        now = time.time()

        if new_state == self.current_state:
            # same state, reset candidate
            self.candidate_state = None
            self.candidate_start_time = None
            return

        # different state detected
        if self.candidate_state == new_state:
            # same candidate as before, check if enough time passed
            elapsed = now - self.candidate_start_time
            if elapsed >= self.min_duration_sec:
                # confirmed! change state
                old_state = self.current_state
                self.current_state = new_state
                self.candidate_state = None
                self.candidate_start_time = None
                self.last_state_change = datetime.now(timezone.utc)

                # trigger callback if we have one
                if self.on_state_change:
                    self.on_state_change(old_state, new_state, self.last_state_change)
        else:
            # new candidate state, start timer
            self.candidate_state = new_state
            self.candidate_start_time = now

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


def get_posture_tracker(on_state_change: Optional[Callable] = None) -> PostureTracker:
    """get the global tracker instance"""
    global _posture_tracker
    if _posture_tracker is None:
        _posture_tracker = PostureTracker(on_state_change=on_state_change)
    elif on_state_change and not _posture_tracker.on_state_change:
        # set callback if provided and not already set
        _posture_tracker.on_state_change = on_state_change
    return _posture_tracker

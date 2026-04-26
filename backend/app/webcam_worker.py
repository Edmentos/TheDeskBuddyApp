"""Low-FPS webcam worker that emits slouch metrics only (no image storage)."""
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class SlouchReading:
    """Derived posture output sent to the app/websocket layer."""
    timestamp: float
    slouch_score: float
    posture_state: str
    confidence: float


@dataclass
class PostureFeatures:
    """Two bounding-box-style signals captured from head + shoulder landmarks.

    ear_span:          horizontal distance between ears in image space (0-1).
                       Grows when the head moves closer to the camera.
    head_shoulder_gap: shoulder_mid_y minus ear_mid_y (positive = head above
                       shoulders, which is normal). Shrinks when the head drops
                       forward toward the desk.
    """
    ts: float
    ear_span: float
    head_shoulder_gap: float
    confidence: float


class WebcamSlouchWorker:
    """Runs MediaPipe Pose at 1-2 FPS and outputs posture features."""

    def __init__(
        self,
        callback: Optional[Callable[[SlouchReading], None]] = None,
        camera_index: int = 0,
        target_fps: float = 1.5,
        reconnect_delay_sec: float = 2.0,
        min_landmark_visibility: float = 0.4,
        score_smoothing_window: int = 3,
        min_state_duration_sec: float = 1.5,
        good_threshold: float = 20.0,
        warning_threshold: float = 50.0,
        min_confidence_for_state: float = 35.0
    ):
        self.callback = callback
        self.camera_index = camera_index
        self.target_fps = max(1.0, min(2.0, target_fps))
        self.reconnect_delay_sec = reconnect_delay_sec
        self.min_landmark_visibility = min_landmark_visibility
        self.min_state_duration_sec = max(0.0, min_state_duration_sec)
        self.good_threshold = good_threshold
        self.warning_threshold = warning_threshold
        self.min_confidence_for_state = min_confidence_for_state

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._latest_reading: Optional[SlouchReading] = None
        self._lock = threading.Lock()

        self._score_history = deque(maxlen=max(1, score_smoothing_window))

        self._stable_state = "unknown"
        self._candidate_state = "unknown"
        self._candidate_since = 0.0

        self._latest_features: Optional[PostureFeatures] = None

        self._baseline: Optional[dict] = None
        # wiggle room as fractions: 0.15 means 15% change allowed before scoring kicks in
        self._tolerances = {
            "ear_span": 0.15,
            "head_drop": 0.15
        }

        self._cap = None
        self._pose = None
        self._cv2 = None
        self._mp_pose = None

    def _load_dependencies(self):
        """Import heavy deps lazily so backend can still boot without webcam libs."""
        import cv2  # pylint: disable=import-outside-toplevel
        import mediapipe as mp  # pylint: disable=import-outside-toplevel

        if not hasattr(mp, "solutions"):
            raise ImportError(
                "Installed mediapipe package does not expose solutions.pose. "
                "Use a compatible release, e.g. mediapipe==0.10.14"
            )

        self._cv2 = cv2
        self._mp_pose = mp.solutions.pose
        self._pose = self._mp_pose.Pose(
            static_image_mode=False,
            model_complexity=0,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

    def _open_camera(self) -> bool:
        """Open camera and report success/failure."""
        video_capture = getattr(self._cv2, "VideoCapture")
        self._cap = video_capture(self.camera_index)
        return bool(self._cap and self._cap.isOpened())

    def _close_camera(self):
        """Release camera handle when we stop or lose connection."""
        if self._cap:
            self._cap.release()
            self._cap = None

    def _landmark_ok(self, lm) -> bool:
        return lm.visibility >= self.min_landmark_visibility

    def _extract_features(
        self,
        landmarks
    ) -> tuple[Optional[PostureFeatures], float]:
        """Extract ear_span and head_shoulder_gap from landmarks.

        Only needs 4 landmarks (ears + shoulders) instead of 7, so success
        rate is significantly higher than the old angle-based approach.
        """
        p = self._mp_pose.PoseLandmark

        req = [
            landmarks[p.LEFT_EAR],
            landmarks[p.RIGHT_EAR],
            landmarks[p.LEFT_SHOULDER],
            landmarks[p.RIGHT_SHOULDER],
        ]

        visibility_vals = [lm.visibility for lm in req]
        confidence = max(
            0.0,
            min(100.0, sum(visibility_vals) / len(visibility_vals) * 100.0)
        )

        if not all(self._landmark_ok(lm) for lm in req):
            return None, confidence

        left_ear = landmarks[p.LEFT_EAR]
        right_ear = landmarks[p.RIGHT_EAR]
        left_shoulder = landmarks[p.LEFT_SHOULDER]
        right_shoulder = landmarks[p.RIGHT_SHOULDER]

        ear_mid_y = (left_ear.y + right_ear.y) / 2.0
        shoulder_mid_y = (left_shoulder.y + right_shoulder.y) / 2.0

        # wider ear span = head is closer to camera = leaning forward
        ear_span = abs(left_ear.x - right_ear.x)

        # in image coords y increases downward, so head-above-shoulders = positive gap;
        # gap shrinks when head drops forward
        head_shoulder_gap = shoulder_mid_y - ear_mid_y

        features = PostureFeatures(
            ts=time.time(),
            ear_span=ear_span,
            head_shoulder_gap=head_shoulder_gap,
            confidence=confidence
        )
        return features, confidence

    def _compute_score(self, features: PostureFeatures) -> Optional[float]:
        """Return slouch score 0-100, or None if no baseline is set yet.

        Score is purely relative to the calibrated baseline:
        - within tolerance band → 0
        - 25% over tolerance on either signal → ~100
        """
        with self._lock:
            baseline = dict(self._baseline) if self._baseline else None
            tolerances = dict(self._tolerances)

        if baseline is None:
            return None

        # how much bigger is the ear span vs calibrated good-posture span
        span_ratio = features.ear_span / max(baseline["ear_span"], 1e-6)
        span_excess = max(0.0, span_ratio - (1.0 + tolerances["ear_span"]))

        # how much has the head-shoulder gap shrunk vs calibrated gap
        baseline_gap = max(baseline["head_shoulder_gap"], 0.01)
        gap_drop_fraction = (baseline_gap - features.head_shoulder_gap) / baseline_gap
        gap_excess = max(0.0, gap_drop_fraction - tolerances["head_drop"])

        # 0.25 excess on either signal = score of 100; weighted equally
        raw = (0.5 * span_excess + 0.5 * gap_excess) / 0.25
        return max(0.0, min(100.0, raw * 100.0))

    def has_baseline(self) -> bool:
        """True if a calibration baseline has been captured."""
        with self._lock:
            return self._baseline is not None

    def get_latest_features(self) -> Optional[PostureFeatures]:
        """Return latest feature vector for calibration/debug endpoints."""
        with self._lock:
            return self._latest_features

    def get_baseline(self) -> Optional[dict]:
        """Return current baseline dict if calibration exists."""
        with self._lock:
            return dict(self._baseline) if self._baseline else None

    def get_tolerances(self) -> dict:
        """Return current tolerance config."""
        with self._lock:
            return dict(self._tolerances)

    def update_tolerances(self, ear_span: float, head_drop: float):
        """Update wiggle-room fractions for each signal."""
        with self._lock:
            self._tolerances = {
                "ear_span": max(0.0, ear_span),
                "head_drop": max(0.0, head_drop)
            }

    def calibrate_baseline(
        self,
        duration_sec: float = 10.0,
        min_samples: int = 4
    ) -> dict:
        """Capture a good-posture baseline from live feature vectors.

        Uses a lower confidence bar than state detection because the user is
        sitting still — a partially-occluded landmark still gives a valid baseline.
        """
        if not self._running:
            raise RuntimeError("Webcam worker is not running")

        deadline = time.time() + max(2.0, duration_sec)
        samples = []
        seen_ts = set()

        cal_min_confidence = max(15.0, self.min_confidence_for_state * 0.4)

        while time.time() < deadline:
            feat = self.get_latest_features()
            if (
                feat
                and feat.confidence >= cal_min_confidence
                and feat.ts not in seen_ts
            ):
                seen_ts.add(feat.ts)
                samples.append(feat)
            time.sleep(0.1)

        if len(samples) < min_samples:
            raise RuntimeError(
                f"Not enough stable webcam samples for baseline "
                f"(got {len(samples)}, need {min_samples}). "
                "Make sure your ears and shoulders are visible and hold still."
            )

        baseline = {
            "ear_span": sum(s.ear_span for s in samples) / len(samples),
            "head_shoulder_gap": sum(s.head_shoulder_gap for s in samples) / len(samples),
            "sample_count": len(samples),
            "captured_at": time.time()
        }

        with self._lock:
            self._baseline = baseline

        return baseline

    def _target_state(self, score: float, confidence: float) -> str:
        """Map score into good/warning/slouching/unknown buckets."""
        if confidence < self.min_confidence_for_state:
            return "unknown"
        if score < self.good_threshold:
            return "good"
        if score < self.warning_threshold:
            return "warning"
        return "slouching"

    def _stable_state_from_target(self, target_state: str, now: float) -> str:
        """Apply minimum-duration gating so posture state does not flicker."""
        if target_state == self._stable_state:
            self._candidate_state = target_state
            self._candidate_since = now
            return self._stable_state

        if target_state != self._candidate_state:
            self._candidate_state = target_state
            self._candidate_since = now
            return self._stable_state

        if now - self._candidate_since >= self.min_state_duration_sec:
            self._stable_state = target_state

        return self._stable_state

    def _smooth_score(self, raw_score: float) -> float:
        """Simple moving average on the continuous score."""
        self._score_history.append(raw_score)
        return sum(self._score_history) / len(self._score_history)

    @staticmethod
    def _reading(now: float, score: float, state: str, conf: float) -> SlouchReading:
        return SlouchReading(
            timestamp=now,
            slouch_score=round(score, 2),
            posture_state=state,
            confidence=round(conf, 2)
        )

    def _run(self):
        """Main loop: capture frame, run pose, emit derived reading, throttle FPS."""
        frame_interval = 1.0 / self.target_fps

        while self._running:
            tick_start = time.time()

            if not self._cap or not self._cap.isOpened():
                if not self._open_camera():
                    time.sleep(self.reconnect_delay_sec)
                    continue

            ok, frame = self._cap.read()
            if not ok or frame is None:
                self._close_camera()
                time.sleep(self.reconnect_delay_sec)
                continue

            cvt_color = getattr(self._cv2, "cvtColor")
            bgr_to_rgb = getattr(self._cv2, "COLOR_BGR2RGB")
            rgb = cvt_color(frame, bgr_to_rgb)
            result = self._pose.process(rgb)

            now = time.time()
            reading = self._reading(now, 0.0, "unknown", 0.0)

            if result.pose_landmarks and result.pose_landmarks.landmark:
                features, conf = self._extract_features(result.pose_landmarks.landmark)
                if features is None:
                    posture_state = self._stable_state_from_target("unknown", now)
                    last_score = self._score_history[-1] if self._score_history else 0.0
                    reading = self._reading(now, last_score, posture_state, conf)
                else:
                    with self._lock:
                        self._latest_features = features

                    score = self._compute_score(features)

                    if score is None:
                        # no baseline yet — hold "unknown" until user calibrates
                        posture_state = self._stable_state_from_target("unknown", now)
                        reading = self._reading(now, 0.0, posture_state, conf)
                    else:
                        smooth_score = self._smooth_score(score)
                        target_state = self._target_state(smooth_score, conf)
                        posture_state = self._stable_state_from_target(target_state, now)
                        reading = self._reading(now, smooth_score, posture_state, conf)
            else:
                posture_state = self._stable_state_from_target("unknown", now)
                last_score = self._score_history[-1] if self._score_history else 0.0
                reading = self._reading(now, last_score, posture_state, 0.0)

            with self._lock:
                self._latest_reading = reading

            if self.callback:
                try:
                    self.callback(reading)
                except (RuntimeError, ValueError, TypeError):
                    pass

            elapsed = time.time() - tick_start
            if elapsed < frame_interval:
                time.sleep(frame_interval - elapsed)

    def start(self):
        """Start background worker thread."""
        if self._running:
            return

        self._load_dependencies()
        self._running = True
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="webcam-slouch-worker"
        )
        self._thread.start()

    def stop(self):
        """Stop thread and release camera/pose resources."""
        if not self._running:
            return

        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None

        self._close_camera()
        if self._pose:
            self._pose.close()
            self._pose = None

    def is_running(self) -> bool:
        """Check if worker loop is active."""
        return self._running

    def get_latest_reading(self) -> Optional[SlouchReading]:
        """Get most recent derived slouch reading."""
        with self._lock:
            return self._latest_reading

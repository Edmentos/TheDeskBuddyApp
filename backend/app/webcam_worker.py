"""Low-FPS webcam worker that emits slouch metrics only (no image storage)."""
import math
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
    """Numeric upper-body features used for score + calibration."""
    ts: float
    head_forward: float
    neck_angle_norm: float
    shoulder_alignment: float
    confidence: float


class WebcamSlouchWorker:
    """Runs MediaPipe Pose at 1-2 FPS and outputs posture features."""

    def __init__(
        self,
        callback: Optional[Callable[[SlouchReading], None]] = None,
        camera_index: int = 0,
        target_fps: float = 1.5,
        reconnect_delay_sec: float = 2.0,
        min_landmark_visibility: float = 0.5,
        score_smoothing_window: int = 5,
        min_state_duration_sec: float = 2.0,
        good_threshold: float = 35.0,
        warning_threshold: float = 60.0,
        min_confidence_for_state: float = 45.0
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

        # Keep a short history so score changes are smooth and less jumpy.
        self._score_history = deque(maxlen=max(1, score_smoothing_window))

        # State gating to avoid fast good/slouching flips frame-to-frame.
        self._stable_state = "unknown"
        self._candidate_state = "unknown"
        self._candidate_since = 0.0

        self._latest_features: Optional[PostureFeatures] = None

        # Baseline is learned from a short "good posture" capture flow.
        self._baseline: Optional[dict] = None
        self._tolerances = {
            "head_forward": 0.08,
            "neck_angle_norm": 0.12,
            "shoulder_alignment": 0.06
        }

        self._cap = None
        self._pose = None
        self._cv2 = None
        self._mp_pose = None

    def _load_dependencies(self):
        """Import heavy deps lazily so backend can still boot without webcam libs."""
        # Local imports keep backend startup resilient if webcam deps are missing.
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
        """Extract normalized posture features from landmarks."""
        p = self._mp_pose.PoseLandmark

        req = [
            landmarks[p.NOSE],
            landmarks[p.LEFT_EAR],
            landmarks[p.RIGHT_EAR],
            landmarks[p.LEFT_SHOULDER],
            landmarks[p.RIGHT_SHOULDER],
            landmarks[p.LEFT_HIP],
            landmarks[p.RIGHT_HIP],
        ]

        visibility_vals = [lm.visibility for lm in req]
        confidence = max(
            0.0,
            min(100.0, sum(visibility_vals) / len(visibility_vals) * 100.0)
        )

        if not all(self._landmark_ok(lm) for lm in req):
            return None, confidence

        nose = landmarks[p.NOSE]
        left_ear = landmarks[p.LEFT_EAR]
        right_ear = landmarks[p.RIGHT_EAR]
        left_shoulder = landmarks[p.LEFT_SHOULDER]
        right_shoulder = landmarks[p.RIGHT_SHOULDER]
        left_hip = landmarks[p.LEFT_HIP]
        right_hip = landmarks[p.RIGHT_HIP]

        ear_mid_x = (left_ear.x + right_ear.x) / 2.0
        shoulder_mid_x = (left_shoulder.x + right_shoulder.x) / 2.0
        shoulder_mid_y = (left_shoulder.y + right_shoulder.y) / 2.0
        hip_mid_x = (left_hip.x + right_hip.x) / 2.0
        hip_mid_y = (left_hip.y + right_hip.y) / 2.0
        ear_mid_y = (left_ear.y + right_ear.y) / 2.0

        shoulder_width = abs(left_shoulder.x - right_shoulder.x) + 1e-6
        torso_len = abs(hip_mid_y - shoulder_mid_y) + 1e-6

        # 1) Head forward relative to shoulders (projected in image plane).
        head_center_x = (nose.x + ear_mid_x) / 2.0
        head_forward = abs(head_center_x - shoulder_mid_x) / shoulder_width

        # 2) Neck angle: angle between neck vector and torso vector.
        neck_vec_x = ear_mid_x - shoulder_mid_x
        neck_vec_y = ear_mid_y - shoulder_mid_y
        torso_vec_x = shoulder_mid_x - hip_mid_x
        torso_vec_y = shoulder_mid_y - hip_mid_y

        neck_mag = math.hypot(neck_vec_x, neck_vec_y) + 1e-6
        torso_mag = math.hypot(torso_vec_x, torso_vec_y) + 1e-6
        dot = (neck_vec_x * torso_vec_x) + (neck_vec_y * torso_vec_y)
        cos_theta = max(-1.0, min(1.0, dot / (neck_mag * torso_mag)))
        neck_angle_deg = math.degrees(math.acos(cos_theta))
        neck_angle_norm = min(1.0, neck_angle_deg / 60.0)

        # 3) Shoulder alignment: large shoulder height gap means asymmetry/lean.
        shoulder_alignment = abs(left_shoulder.y - right_shoulder.y) / torso_len

        features = PostureFeatures(
            ts=time.time(),
            head_forward=head_forward,
            neck_angle_norm=neck_angle_norm,
            shoulder_alignment=shoulder_alignment,
            confidence=confidence
        )
        return features, confidence

    def _compute_score(self, features: PostureFeatures) -> float:
        """Compute continuous score, baseline-aware if calibration exists."""
        if self._baseline:
            hf_lim = self._baseline["head_forward"] + self._tolerances["head_forward"]
            na_lim = self._baseline["neck_angle_norm"] + self._tolerances["neck_angle_norm"]
            sa_lim = self._baseline["shoulder_alignment"] + self._tolerances["shoulder_alignment"]

            hf = max(0.0, features.head_forward - hf_lim)
            na = max(0.0, features.neck_angle_norm - na_lim)
            sa = max(0.0, features.shoulder_alignment - sa_lim)
            raw_score = (0.45 * hf) + (0.35 * na) + (0.20 * sa)
            return max(0.0, min(100.0, raw_score * 260.0))

        raw_score = (
            (0.45 * features.head_forward) +
            (0.35 * features.neck_angle_norm) +
            (0.20 * features.shoulder_alignment)
        )
        return max(0.0, min(100.0, raw_score * 100.0))

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

    def update_tolerances(
        self,
        head_forward: float,
        neck_angle_norm: float,
        shoulder_alignment: float
    ):
        """Update tolerance values used when comparing against baseline."""
        with self._lock:
            self._tolerances = {
                "head_forward": max(0.0, head_forward),
                "neck_angle_norm": max(0.0, neck_angle_norm),
                "shoulder_alignment": max(0.0, shoulder_alignment)
            }

    def calibrate_baseline(
        self,
        duration_sec: float = 6.0,
        min_samples: int = 6
    ) -> dict:
        """Capture a short good-posture baseline from live feature vectors."""
        if not self._running:
            raise RuntimeError("Webcam worker is not running")

        deadline = time.time() + max(2.0, duration_sec)
        samples = []
        seen_ts = set()

        while time.time() < deadline:
            feat = self.get_latest_features()
            if (
                feat
                and feat.confidence >= self.min_confidence_for_state
                and feat.ts not in seen_ts
            ):
                seen_ts.add(feat.ts)
                samples.append(feat)
            time.sleep(0.2)

        if len(samples) < min_samples:
            raise RuntimeError("Not enough stable webcam samples for baseline")

        baseline = {
            "head_forward": sum(s.head_forward for s in samples) / len(samples),
            "neck_angle_norm": (
                sum(s.neck_angle_norm for s in samples) / len(samples)
            ),
            "shoulder_alignment": (
                sum(s.shoulder_alignment for s in samples) / len(samples)
            ),
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
        """Small helper to keep reading creation concise."""
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
                # If camera drops, release and retry after delay.
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
                    target_state = self._target_state(0.0, conf)
                    posture_state = self._stable_state_from_target(target_state, now)
                    last_score = self._score_history[-1] if self._score_history else 0.0
                    reading = self._reading(now, last_score, posture_state, conf)
                else:
                    with self._lock:
                        self._latest_features = features

                    raw_score = self._compute_score(features)
                    smooth_score = self._smooth_score(raw_score)
                    target_state = self._target_state(smooth_score, conf)
                    posture_state = self._stable_state_from_target(target_state, now)
                    reading = self._reading(now, smooth_score, posture_state, conf)
            else:
                # No person in frame -> report unknown; keep score stable by not appending 0.
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

"""Low-FPS webcam worker that emits slouch metrics only (no image storage)."""
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class SlouchReading:
    """Derived posture output sent to the app/websocket layer."""
    timestamp: float
    slouch_score: float
    posture_state: str
    confidence: float


class WebcamSlouchWorker:
    """Runs MediaPipe Pose at 1-2 FPS and outputs slouch features."""

    def __init__(
        self,
        callback: Optional[Callable[[SlouchReading], None]] = None,
        camera_index: int = 0,
        target_fps: float = 1.5,
        reconnect_delay_sec: float = 2.0,
        min_landmark_visibility: float = 0.5
    ):
        self.callback = callback
        self.camera_index = camera_index
        self.target_fps = max(1.0, min(2.0, target_fps))
        self.reconnect_delay_sec = reconnect_delay_sec
        self.min_landmark_visibility = min_landmark_visibility

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._latest_reading: Optional[SlouchReading] = None
        self._lock = threading.Lock()

        self._cap = None
        self._pose = None
        self._cv2 = None
        self._mp_pose = None

    def _load_dependencies(self):
        """Import heavy deps lazily so backend can still boot without webcam libs."""
        import cv2
        import mediapipe as mp

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

    def _compute_score(self, landmarks) -> tuple[float, float]:
        """Compute a simple slouch heuristic from head/ear/shoulder/hip landmarks."""
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
        confidence = max(0.0, min(100.0, sum(visibility_vals) / len(visibility_vals) * 100.0))

        if not all(self._landmark_ok(lm) for lm in req):
            return 0.0, confidence

        nose = landmarks[p.NOSE]
        left_ear = landmarks[p.LEFT_EAR]
        right_ear = landmarks[p.RIGHT_EAR]
        left_shoulder = landmarks[p.LEFT_SHOULDER]
        right_shoulder = landmarks[p.RIGHT_SHOULDER]
        left_hip = landmarks[p.LEFT_HIP]
        right_hip = landmarks[p.RIGHT_HIP]

        shoulder_mid_x = (left_shoulder.x + right_shoulder.x) / 2.0
        shoulder_mid_y = (left_shoulder.y + right_shoulder.y) / 2.0
        hip_mid_y = (left_hip.y + right_hip.y) / 2.0
        ear_mid_y = (left_ear.y + right_ear.y) / 2.0

        shoulder_width = abs(left_shoulder.x - right_shoulder.x) + 1e-6
        torso_len = abs(hip_mid_y - shoulder_mid_y) + 1e-6

        # Simple heuristic: if head landmarks drop toward shoulder line, score goes up.
        head_drop = max(0.0, (nose.y - shoulder_mid_y) / torso_len)
        ear_drop = max(0.0, (ear_mid_y - shoulder_mid_y) / torso_len)
        head_drift = abs(nose.x - shoulder_mid_x) / shoulder_width

        raw_score = (0.55 * head_drop) + (0.30 * ear_drop) + (0.15 * head_drift)
        slouch_score = max(0.0, min(100.0, raw_score * 100.0))
        return slouch_score, confidence

    @staticmethod
    def _state_from_score(score: float) -> str:
        if score < 35.0:
            return "upright"
        if score < 60.0:
            return "warning"
        return "slouch"

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
            reading = SlouchReading(timestamp=now, slouch_score=0.0, posture_state="no_person", confidence=0.0)

            if result.pose_landmarks and result.pose_landmarks.landmark:
                score, conf = self._compute_score(result.pose_landmarks.landmark)
                reading = SlouchReading(
                    timestamp=now,
                    slouch_score=round(score, 2),
                    posture_state=self._state_from_score(score),
                    confidence=round(conf, 2)
                )

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
        self._thread = threading.Thread(target=self._run, daemon=True, name="webcam-slouch-worker")
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

"""Audio worker for mic input and RMS noise level calculation."""
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np
import sounddevice as sd


@dataclass
class NoiseLevel:
    """Noise level measurement."""
    rms: float
    db: float
    smoothed_db: float
    timestamp: float


class AudioWorker:
    """Captures audio and calculates RMS noise levels with smoothing."""

    def __init__(
        self,
        sample_rate: int = 44100,
        block_duration: float = 0.1,
        callback: Optional[Callable[[NoiseLevel], None]] = None,
        calibration_factor: float = 94.0,
        smoothing_window: int = 5
    ):
        self.sample_rate = sample_rate
        self.block_duration = block_duration
        self.block_size = int(sample_rate * block_duration)
        self.callback = callback
        self.calibration_factor = calibration_factor
        self._rms_history = deque(maxlen=smoothing_window)
        self._stream: Optional[sd.InputStream] = None
        self._running = False
        self._latest_noise_level: Optional[NoiseLevel] = None

    def _audio_callback(self, indata, _frames, _time_info, status):
        """Process audio blocks and calculate noise levels."""
        if status:
            print(f"Audio status: {status}")

        audio_data = indata[:, 0]
        rms = np.sqrt(np.mean(audio_data**2))

        # Convert to dB with calibration
        db = self.calibration_factor + 20 * np.log10(rms + 1e-10)

        # Add to smoothing history
        self._rms_history.append(rms)

        # Calculate smoothed dB from RMS history
        smoothed_rms = sum(self._rms_history) / len(self._rms_history)
        smoothed_db = self.calibration_factor + 20 * np.log10(
            smoothed_rms + 1e-10
        )

        noise_level = NoiseLevel(
            rms=float(rms),
            db=float(db),
            smoothed_db=float(smoothed_db),
            timestamp=time.time()
        )

        self._latest_noise_level = noise_level

        if self.callback:
            try:
                self.callback(noise_level)
            except (ValueError, TypeError, RuntimeError) as e:
                print(f"Callback error: {e}")

    def start(self):
        """Start audio capture."""
        if self._running:
            return

        self._running = True
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            blocksize=self.block_size,
            channels=1,
            callback=self._audio_callback
        )
        self._stream.start()

    def stop(self):
        """Stop audio capture."""
        if not self._running:
            return

        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def get_latest_noise_level(self) -> Optional[NoiseLevel]:
        """Get the most recent noise level."""
        return self._latest_noise_level

    def is_running(self) -> bool:
        """Check if capturing audio."""
        return self._running

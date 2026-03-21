"""Main FastAPI app for DeskBuddy."""
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api import readings, serial, settings
from app.audio_worker import AudioWorker, NoiseLevel
from app.db.database import check_db_connection
from app.db.persistence import save_reading_to_db, save_noise_reading_to_db
from app.serial.serial_reader import esp32_reader
from app.webcam_worker import SlouchReading, WebcamSlouchWorker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages websocket connections for live data streaming."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept and add new websocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket connected. Total: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        """Remove websocket from active connections."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info("WebSocket disconnected. Total: %d", len(self.active_connections))

    async def broadcast(self, data: dict):
        """Send data to all connected clients."""
        if not self.active_connections:
            return

        message = json.dumps(data)
        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except (RuntimeError, ConnectionError) as e:
                logger.warning("Send failed: %s", e)
                disconnected.append(connection)

        for connection in disconnected:
            self.disconnect(connection)


# Module-level state
manager = ConnectionManager()


class AppState:
    """Holds app-level state."""
    event_loop: Optional[asyncio.AbstractEventLoop] = None
    audio_worker: Optional[AudioWorker] = None
    webcam_worker: Optional[WebcamSlouchWorker] = None


state = AppState()


def on_reading_callback(data: dict):
    """Handle incoming sensor data from ESP32."""
    try:
        save_reading_to_db(data)
        if state.event_loop and manager.active_connections:
            asyncio.run_coroutine_threadsafe(
                manager.broadcast(data), state.event_loop
            )
    except (ValueError, RuntimeError) as e:
        logger.error("Reading error: %s", e)


def on_noise_callback(noise_level: NoiseLevel):
    """Handle incoming noise data from audio worker."""
    try:
        save_noise_reading_to_db(smoothed_db=noise_level.smoothed_db)

        noise_data = {
            "sensor": "noise_db",
            "value": round(noise_level.smoothed_db, 1),
            "rms": round(noise_level.rms, 4),
            "db": round(noise_level.db, 1),
            "timestamp": noise_level.timestamp
        }

        if state.event_loop and manager.active_connections:
            asyncio.run_coroutine_threadsafe(
                manager.broadcast(noise_data), state.event_loop
            )
    except (ValueError, RuntimeError) as e:
        logger.error("Noise error: %s", e)


def on_slouch_callback(reading: SlouchReading):
    """Handle incoming webcam slouch readings."""
    slouch_data = {
        "timestamp": reading.timestamp,
        "slouch_score": reading.slouch_score,
        "posture_state": reading.posture_state,
        "confidence": reading.confidence
    }

    if state.event_loop and manager.active_connections:
        try:
            asyncio.run_coroutine_threadsafe(
                manager.broadcast(slouch_data), state.event_loop
            )
        except RuntimeError as e:
            logger.error("Slouch broadcast error: %s", e)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Handle startup and shutdown events."""
    logger.info("Starting up...")
    state.event_loop = asyncio.get_running_loop()
    esp32_reader.on_reading = on_reading_callback

    try:
        state.audio_worker = AudioWorker(
            sample_rate=44100,
            block_duration=0.5,
            callback=on_noise_callback,
            calibration_factor=94.0,
            smoothing_window=10
        )
        state.audio_worker.start()
        logger.info("Audio worker started")
    except (RuntimeError, OSError) as e:
        logger.warning("Audio worker failed: %s", e)

    try:
        state.webcam_worker = WebcamSlouchWorker(
            callback=on_slouch_callback,
            camera_index=0,
            target_fps=1.5,
            reconnect_delay_sec=2.0,
            min_landmark_visibility=0.5
        )
        state.webcam_worker.start()
        logger.info("Webcam slouch worker started")
    except (RuntimeError, OSError, ImportError) as e:
        logger.warning("Webcam slouch worker failed: %s", e)

    yield

    logger.info("Shutting down...")
    esp32_reader.disconnect()
    if state.audio_worker and state.audio_worker.is_running():
        state.audio_worker.stop()
    if state.webcam_worker and state.webcam_worker.is_running():
        state.webcam_worker.stop()


app = FastAPI(title="DeskBuddy API", lifespan=lifespan)

app.include_router(readings.router)
app.include_router(serial.router)
app.include_router(settings.router)

# allow frontend to hit our api
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Check if backend and db are working."""
    return {
        "status": "ok",
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "db_ok": check_db_connection()
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "DeskBuddy API is running"}


@app.websocket("/stream")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for streaming live sensor data."""
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

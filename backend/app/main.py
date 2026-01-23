# main fastapi app
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api import readings, serial
from app.db.database import check_db_connection
from app.db.persistence import save_reading_to_db
from app.serial.serial_reader import esp32_reader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConnectionManager:
    # handles websocket connections

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket client connected. Total: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info("WebSocket client disconnected. Total: %d", len(self.active_connections))

    async def broadcast(self, data: dict):
        # send data to all connected clients
        if not self.active_connections:
            return

        message = json.dumps(data)
        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except (RuntimeError, ConnectionError) as e:
                logger.warning("Failed to send to client: %s", e)
                disconnected.append(connection)

        for connection in disconnected:
            self.disconnect(connection)


manager = ConnectionManager()
EVENT_LOOP = None  # yeah yeah i know globals are bad


def on_reading_callback(data: dict):
    # gets called whenever ESP32 sends data
    try:
        save_reading_to_db(data)
    except (ValueError, RuntimeError) as e:
        logger.error("Failed to save reading: %s", e)

    # broadcast to websocket clients
    if EVENT_LOOP:
        try:
            asyncio.run_coroutine_threadsafe(manager.broadcast(data), EVENT_LOOP)
        except RuntimeError as e:
            logger.error("Failed to broadcast: %s", e)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # startup/shutdown stuff
    global EVENT_LOOP
    logger.info("Starting up...")
    EVENT_LOOP = asyncio.get_running_loop()
    esp32_reader.on_reading = on_reading_callback
    yield
    logger.info("Shutting down...")
    esp32_reader.disconnect()


app = FastAPI(title="DeskBuddy API", lifespan=lifespan)

app.include_router(readings.router)
app.include_router(serial.router)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    # check if everything is working
    db_ok = check_db_connection()
    return {
        "status": "ok",
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "db_ok": db_ok
    }


@app.get("/")
async def root():
    return {"message": "DeskBuddy API is running"}


@app.websocket("/stream")
async def websocket_endpoint(websocket: WebSocket):
    # websocket for streaming sensor data
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

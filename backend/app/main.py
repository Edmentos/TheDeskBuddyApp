import asyncio
import logging
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import check_db_connection
<<<<<<< HEAD
from app.api import readings, serial
=======
from app.api import readings
from app.serial_reader import read_loop
>>>>>>> 1c9d3e33955ef50b56532bb0458b2aa690686ba8

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and broadcasts"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("Client connected. Total: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info("Client disconnected. Total: %d", len(self.active_connections))

    async def broadcast(self, data: Dict[str, Any]):
        """
        Broadcast data to all connected clients.
        Non-blocking: failures to send don't crash the server.
        """
        if not self.active_connections:
            return

        message = json.dumps(data)
        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.warning("Failed to send to client: %s", e)
                disconnected.append(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)


# Global connection manager
manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup: Start serial reader in background thread
    logger.info("Starting serial reader thread...")

    # Capture the main event loop
    loop = asyncio.get_running_loop()

    def broadcast_callback(reading):
        """Callback to broadcast readings via WebSocket"""
        try:
            # Schedule broadcast in the main event loop from another thread
            asyncio.run_coroutine_threadsafe(manager.broadcast(reading), loop)
        except Exception as e:
            logger.error("Broadcast error: %s", e)

    import threading
    serial_thread = threading.Thread(
        target=lambda: read_loop(on_reading=broadcast_callback),
        daemon=True
    )
    serial_thread.start()
    logger.info("Serial reader started")

    yield

    # Shutdown
    logger.info("Shutting down...")


app = FastAPI(title="DeskBuddy API", lifespan=lifespan)

# Include routers
app.include_router(readings.router)
app.include_router(serial.router)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Health check endpoint with database connectivity test"""
    db_ok = check_db_connection()
    return {
        "status": "ok",
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "db_ok": db_ok
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "DeskBuddy API is running"}


@app.websocket("/stream")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live sensor data streaming"""
    await manager.connect(websocket)
    try:
        # Keep connection alive
        while True:
            # Wait for any message from client (keeps connection open)
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error("WebSocket error: %s", e)
        manager.disconnect(websocket)

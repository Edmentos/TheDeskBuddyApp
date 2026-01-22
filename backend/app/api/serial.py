"""API endpoints for ESP32 serial communication."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.serial.serial_reader import esp32_reader

router = APIRouter(prefix="/serial", tags=["serial"])


class ConnectRequest(BaseModel):
    """Request model for serial port connection."""

    port: str
    baudrate: int = 115200


@router.get("/ports")
async def list_ports():
    """List all available serial ports"""
    try:
        ports = esp32_reader.list_available_ports()
        return {"ports": ports}
    except (OSError, RuntimeError) as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list ports: {str(e)}"
        ) from e


@router.post("/connect")
async def connect(request: ConnectRequest):
    """Connect to ESP32 on specified port"""
    success = esp32_reader.connect(request.port, request.baudrate)
    if success:
        return {
            "status": "connected",
            "port": request.port,
            "baudrate": request.baudrate
        }
    raise HTTPException(
        status_code=400,
        detail=(
            f"Failed to connect to {request.port}. "
            "Check that the port is correct, the device is "
            "connected, and you have proper permissions."
        )
    )


@router.post("/auto-connect")
async def auto_connect(baudrate: int = 115200):
    """Automatically detect and connect to ESP32"""
    esp32_port = esp32_reader.find_esp32_port()
    if not esp32_port:
        raise HTTPException(
            status_code=404,
            detail="No ESP32 device found. Make sure it's plugged in and drivers are installed."
        )

    success = esp32_reader.connect(esp32_port, baudrate)
    if success:
        return {
            "status": "connected",
            "port": esp32_port,
            "baudrate": baudrate,
            "auto_detected": True
        }
    raise HTTPException(
        status_code=400,
        detail=f"Found ESP32 on {esp32_port} but failed to connect."
    )


@router.post("/disconnect")
async def disconnect():
    """Disconnect from ESP32"""
    try:
        esp32_reader.disconnect()
        return {"status": "disconnected"}
    except (OSError, RuntimeError) as e:
        raise HTTPException(
            status_code=500,
            detail=f"Disconnect error: {str(e)}"
        ) from e


@router.get("/status")
async def get_status():
    """Get current ESP32 connection status"""
    return esp32_reader.get_status()


@router.get("/data")
async def get_data():
    """Get latest data from ESP32"""
    data = esp32_reader.get_latest_data()
    status = esp32_reader.get_status()

    return {
        "connected": status["connected"],
        "port": status["port"],
        "data": data
    }

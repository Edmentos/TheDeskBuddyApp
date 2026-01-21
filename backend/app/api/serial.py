from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.serial.serial_reader import esp32_reader

router = APIRouter(prefix="/serial", tags=["serial"])


class ConnectRequest(BaseModel):
    port: str
    baudrate: int = 115200


@router.get("/ports")
async def list_ports():
    """List all available serial ports"""
    try:
        ports = esp32_reader.list_available_ports()
        return {"ports": ports}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list ports: {str(e)}")


@router.post("/connect")
async def connect(request: ConnectRequest):
    """Connect to ESP32 on specified port"""
    try:
        success = esp32_reader.connect(request.port, request.baudrate)
        if success:
            return {
                "status": "connected",
                "port": request.port,
                "baudrate": request.baudrate
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to connect to {request.port}. Check that the port is correct, the device is connected, and you have proper permissions."
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection error: {str(e)}")


@router.post("/disconnect")
async def disconnect():
    """Disconnect from ESP32"""
    try:
        esp32_reader.disconnect()
        return {"status": "disconnected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Disconnect error: {str(e)}")


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

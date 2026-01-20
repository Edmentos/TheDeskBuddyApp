from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import check_db_connection
from app.api import readings

app = FastAPI(title="DeskBuddy API")

# Include routers
app.include_router(readings.router)

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

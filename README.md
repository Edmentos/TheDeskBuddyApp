# DeskBuddy

A desk monitoring app that tracks sitting/standing posture, webcam slouch detection, ambient noise levels, and environmental sensor data (temperature, humidity, distance) from an ESP32. Data streams live to a React dashboard over WebSocket and is stored in PostgreSQL for historical queries.

## Features

- **Live sensor dashboard** — temperature, humidity, distance streamed over WebSocket from ESP32
- **Sitting/standing detection** — ultrasonic distance with moving average smoothing, hysteresis, and minimum-duration gating to prevent flickering
- **Webcam slouch detection** — MediaPipe Pose runs at 1–2 FPS, scores forward lean based on ear/shoulder landmarks, emits good/warning/slouching state
- **Noise level monitoring** — microphone RMS → dB with moving average smoothing, configurable quiet/normal/loud thresholds
- **History charts** — Recharts line graphs for temperature, humidity, and distance with 1h/6h/24h/7d time range filters
- **CSV export** — download any sensor's data filtered by date range
- **Posture stats** — daily sitting vs. standing time with percentages
- **Settings page** — desk height calibration, webcam baseline capture, noise threshold config

## Project structure

```
backend/
  app/
    api/          # FastAPI routers (readings, settings, serial)
    db/           # SQLAlchemy models, migrations, session management
    serial/       # ESP32 serial reader with auto-reconnect
    audio_worker.py     # Microphone capture and RMS/dB calculation
    webcam_worker.py    # MediaPipe Pose slouch detection
    posture.py          # Sitting/standing state machine
    posture_events.py   # Writes posture transitions to DB
    main.py             # App entry point, WebSocket stream, worker startup
  tests/
    test_serial_parsing.py  # Regex and ESP32 detection unit tests
    test_posture.py         # State machine unit tests
    test_api.py             # API endpoint integration tests

frontend/
  src/
    pages/        # Dashboard, History, Settings
    services/     # API client (api.js)
    hooks/        # useDeskBuddyStream (WebSocket hook)
```

## Requirements

- Python 3.11+
- Node.js 18+
- Docker (for PostgreSQL)
- ESP32 with CP210x or CH340 USB-serial chip
- Webcam (optional — app degrades gracefully without one)

## Setup

### 1. Start PostgreSQL

```bash
docker-compose up -d
```

Runs PostgreSQL on `localhost:5432`. Credentials are all `deskbuddy` (user/password/database).

### 2. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

### 3. Run everything

```bash
# from project root
start.bat
```

Or manually:

```bash
# terminal 1 — backend
cd backend && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# terminal 2 — frontend
cd frontend && npm install && npm run dev
```

- Backend: http://127.0.0.1:8000
- Frontend: http://localhost:5173
- Health check: http://127.0.0.1:8000/health

## ESP32 data format

The ESP32 should send JSON over serial at 115200 baud:

```json
{"ts_ms": 76336, "distance_cm": 99.8, "temp_c": 17.8, "hum_pct": 59}
```

`ts_ms` is the device uptime in milliseconds. The other three fields are optional — if a sensor fails to read, omit that key and the backend will skip it gracefully.

## Calibration

### Sitting/standing detection

1. Go to **Settings → Automatic Calibration**
2. Sit at your desk, click **Record Sitting Height**
3. Raise the desk to standing height, click **Record Standing Height**
4. Click **Save Calibration** — the threshold is set to the midpoint

You can also manually enter heights in the Posture Detection section and hit Save.

### Webcam slouch detection

1. Go to **Settings → Webcam Posture Calibration**
2. Sit up straight with ears and shoulders visible to the camera
3. Click **Calibrate Good Posture (10s)** and hold still
4. Adjust ear span / head drop tolerances if you're getting false positives

The baseline captures your ear span and head-shoulder gap in image coordinates. Live readings are scored relative to that baseline.

## Running tests

```bash
cd backend
pip install pytest httpx
pytest tests/ -v
```

Tests use an in-memory SQLite database so you don't need PostgreSQL running.

## Logs

The backend writes to `backend/backend.log` with automatic rotation (5MB cap, 3 backups). Useful for diagnosing serial disconnects, webcam failures, or DB errors that happen while the terminal isn't open.

## Troubleshooting

**ESP32 not detected**
- Check Device Manager for the COM port
- Install CP210x or CH340 drivers if it shows as unknown device
- Try the manual port selector in the Dashboard if auto-connect fails

**Webcam not working**
- Make sure no other app has the camera open
- Use the "Pause & Preview" button in the Dashboard to check if the camera feed works — the backend worker holds the camera exclusively

**No audio data**
- Check that your default microphone is set correctly in Windows Sound Settings
- The app uses whatever device is set as default — there's no device picker currently

**PostgreSQL connection failed**
- Make sure Docker Desktop is running before starting the backend
- Run `docker-compose up -d` from the project root
- Check `docker ps` to confirm the container is up

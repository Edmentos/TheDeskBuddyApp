# DeskBuddy

A desk monitoring application that reads sensor data from ESP32 and displays it in a web dashboard.

## Project Structure

```
backend/          - fastapi server
  app/
    api/          - endpoints
    db/           - postgres models
    serial/       - reads from ESP32
    main.py       - main app file
frontend/         - react app
  src/
    pages/        - dashboard, history, settings
    services/     - api calls
```

## What you need

- Python 3.10+ (i used 3.11)
- Node.js 18+
- Docker
- ESP32 with usb serial (CP210x or CH340)

## How to run

### 1. Database
```bash
docker-compose up -d
```
runs postgres on localhost:5432 (user/pass/db all = deskbuddy)

### 2. Backend setup
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate    # windows
# source .venv/bin/activate  # mac/linux
pip install -r requirements.txt
```

### 3. Run backend
```bash
uvicorn app.main:app --reload
```
goes to http://127.0.0.1:8000

check if its working: http://127.0.0.1:8000/health

### 4. Frontend
```bash
cd frontend
npm install
npm run dev
```
opens on http://localhost:5173

## Some notes

### Backend stuff
- FastAPI
- postgres + sqlalchemy
- serial reader finds ESP32 automatically (looks for CP210x/CH340)
- reads at 115200 baud

ESP32 needs to send json like:
```json
{"ts_ms":76336,"distance_cm":99.8,"temp_c":17.8,"hum_pct":59}
```

### Frontend
- react + vite
- has dashboard, history, settings pages (history & settings not done yet lol)
- calls backend at http://127.0.0.1:8000

### Database stuff
stop db: `docker-compose down`
reset db (deletes everything): `docker-compose down -v`

### Features
- auto finds ESP32 port
- reconnects if it disconnects
- saves to postgres
- websocket for live updates

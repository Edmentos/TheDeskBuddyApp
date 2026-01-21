# DeskBuddy

A desk monitoring application that reads sensor data from ESP32 and displays it in a web dashboard.

## Project Structure

```
The_Desk_Buddy/
├── backend/          # Python FastAPI backend
│   ├── app/
│   │   ├── api/          # API endpoints
│   │   ├── config/       # Settings
│   │   ├── db/           # Database models (PostgreSQL)
│   │   ├── serial_reader.py  # ESP32 serial reader
│   │   └── main.py       # FastAPI entry point
│   ├── requirements.txt
│   └── .env.example
├── frontend/         # React + Vite frontend
│   ├── src/
│   │   ├── pages/    # Dashboard, History, Settings
│   │   ├── services/ # API client
│   │   └── ...
│   └── package.json
├── docker-compose.yml
└── README.md
```

## Prerequisites

- Python 3.10+
- Node.js 18+
- Docker & Docker Compose
- ESP32 device with CP210x or CH340 USB-to-serial chip

## Quick Start

### 1. Start PostgreSQL Database

```bash
docker-compose up -d
```

PostgreSQL will run on `localhost:5432` with:
- Database: `deskbuddy`
- User: `deskbuddy`
- Password: `deskbuddy`

### 2. Setup Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
copy .env.example .env  # Windows
# cp .env.example .env  # macOS/Linux
```

### 3. Run Backend

**Option A: FastAPI + Serial Reader (Recommended)**
```bash
# Terminal 1 - API Server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 - Serial Reader (reads ESP32 data)
python -m app.serial_reader
```

**Option B: FastAPI only (no ESP32 data)**
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend API: `http://127.0.0.1:8000`  
Health check: `http://127.0.0.1:8000/health`

### 4. Start Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Frontend: `http://localhost:5173`

## Development

### Backend

- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy
- **Serial Reader**: Auto-detects ESP32 on CP210x/CH340, reads JSON sensor data at 115200 baud
- **Health endpoint**: `GET /health` returns `{status, time_utc, db_ok}`

### ESP32 Data Format

The serial reader expects JSON lines from ESP32:
```json
{"ts_ms":76336,"distance_cm":99.8,"temp_c":17.8,"hum_pct":59}
```

Lines can have timestamp prefixes (e.g., `17:09:47.625 -> {...}`), which are automatically stripped.

### Frontend

- **Framework**: React 18 with Vite
- **Routing**: react-router-dom
- **Pages**: 
  - Dashboard: Shows backend health status
  - History: View sensor data
  - Settings: Configuration
- **API Service**: Configured to call backend at `http://127.0.0.1:8000`

### Database Management

Stop database:
```bash
docker-compose down
```

Reset database (deletes all data):
```bash
docker-compose down -v
```

### Serial Reader Features

- Auto-detects ESP32 USB port (CP210x/CH340/ESP32 keywords)
- Auto-reconnects every 2s if disconnected
- Handles malformed JSON gracefully
- Persists readings to PostgreSQL (distance, temperature, humidity)
- Logs all readings to console

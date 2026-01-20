# DeskBuddy

Week 1 monorepo scaffold for DeskBuddy - A desk monitoring and productivity application.

## Project Structure

```
The_Desk_Buddy/
├── backend/          # Python FastAPI backend
│   ├── app/
│   │   ├── api/      # API routers (placeholder)
│   │   ├── audio/    # Audio processing (placeholder)
│   │   ├── config/   # Configuration (placeholder)
│   │   ├── db/       # Database models and session
│   │   ├── serial/   # Serial device reader (placeholder)
│   │   ├── vision/   # Computer vision (placeholder)
│   │   ├── websocket/# WebSocket stream manager (placeholder)
│   │   └── main.py   # FastAPI entry point
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

## Quick Start

### 1. Start PostgreSQL

```bash
docker-compose up -d
```

This starts PostgreSQL on `localhost:5432` with:
- Database: `deskbuddy`
- User: `deskbuddy`
- Password: `deskbuddy`

### 2. Start Backend

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

# Copy environment file
copy .env.example .env  # Windows
# cp .env.example .env  # macOS/Linux

# Run the server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend will be available at: `http://127.0.0.1:8000`

Health check endpoint: `http://127.0.0.1:8000/health`

### 3. Start Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Frontend will be available at: `http://localhost:5173`

## Development

### Backend

- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy
- **Health endpoint**: Returns `{status, time_utc, db_ok}` with database connectivity test

### Frontend

- **Framework**: React 18 with Vite
- **Routing**: react-router-dom
- **Pages**: Dashboard (shows backend health status), History, Settings
- **API Service**: Configured to call backend at `http://127.0.0.1:8000`

### Database

To stop the database:
```bash
docker-compose down
```

To reset the database (removes all data):
```bash
docker-compose down -v
```

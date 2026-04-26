@echo off
echo Starting DeskBuddy Application...
echo.

REM Start Docker containers
echo Starting Docker containers...
docker-compose up -d
if %errorlevel% neq 0 (
    echo ERROR: Failed to start Docker. Make sure Docker Desktop is running.
    pause
    exit /b 1
)

REM Brief pause so Docker has time to start the postgres process before init_db
REM tries to connect. init_db now retries internally so a 3s head-start is enough.
cmd /c "timeout /t 3 /nobreak >nul"

REM Initialize database tables
echo Initializing database tables...
cd /d %~dp0backend
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    python -m app.db.init_db
    call deactivate
) else (
    python -m app.db.init_db
)
cd ..

REM Start backend in new window with venv activated
echo Starting Backend Server...
start "DeskBuddy Backend" cmd /k "cd /d %~dp0backend && call venv\Scripts\activate.bat && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

REM Wait a bit for backend to start
cmd /c "timeout /t 3 /nobreak >nul"

REM Start frontend in new window
echo Starting Frontend Dev Server...
start "DeskBuddy Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ====================================
echo DeskBuddy is starting!
echo Backend: http://127.0.0.1:8000
echo Frontend: http://localhost:5173
echo ====================================
echo.
echo Close this window or press any key to exit...
pause >nul

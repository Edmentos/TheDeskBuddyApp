@echo off
echo Stopping DeskBuddy Application...

REM Kill backend processes by window title first
taskkill /FI "WindowTitle eq DeskBuddy Backend*" /T /F 2>nul

REM Kill frontend processes by window title first
taskkill /FI "WindowTitle eq DeskBuddy Frontend*" /T /F 2>nul

REM Force kill any remaining Python processes running uvicorn
echo Stopping backend processes...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000"') do (
    taskkill /PID %%a /F 2>nul
)

REM Force kill any remaining Node processes on port 5173
echo Stopping frontend processes...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173"') do (
    taskkill /PID %%a /F 2>nul
)

REM Stop Docker containers
echo Stopping Docker containers...
docker-compose down

echo.
echo DeskBuddy stopped.
pause

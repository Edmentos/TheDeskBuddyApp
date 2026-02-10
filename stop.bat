@echo off
echo Stopping DeskBuddy Application...

REM Stop Docker containers (this is the safe way)
echo Stopping Docker containers...
docker-compose down

echo.
echo DeskBuddy stopped.
echo.
echo Note: If backend/frontend processes are still running,
echo close their terminal windows manually.
pause

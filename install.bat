@echo off
echo Installing DeskBuddy Dependencies...
echo.

REM Create virtual environment if it doesn't exist
if not exist "%~dp0backend\venv" (
    echo Creating Python virtual environment...
    cd /d %~dp0backend
    python -m venv venv
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
    cd ..
)

REM Install backend dependencies
echo Installing Python packages...
cd /d %~dp0backend
call venv\Scripts\activate.bat
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install Python dependencies
    pause
    exit /b 1
)
call deactivate
cd ..

echo.

REM Install frontend dependencies
echo Installing Node packages...
cd /d %~dp0frontend
call npm install
if %errorlevel% neq 0 (
    echo ERROR: Failed to install Node dependencies
    pause
    exit /b 1
)
cd ..

echo.
echo ====================================
echo Installation complete!
echo Run start.bat to launch DeskBuddy
echo ====================================
pause

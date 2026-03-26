@echo off
echo ============================================================
echo Interview Anti-Cheating System - Quick Start
echo ============================================================
echo.

echo Checking Python...
python --version
if errorlevel 1 (
    echo Python not found! Please install Python 3.9+
    pause
    exit /b
)

echo.
echo Checking Node.js...
node --version
if errorlevel 1 (
    echo Node.js not found! Please install Node.js 18+
    pause
    exit /b
)

echo.
echo ============================================================
echo Step 1: Installing Backend Dependencies
echo ============================================================
cd backend
echo Installing Python packages...
pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install backend dependencies
    pause
    exit /b
)

echo.
echo ============================================================
echo Step 2: Installing Frontend Dependencies
echo ============================================================
cd ..\frontend
echo Installing Node packages (this may take a few minutes)...
call npm install
if errorlevel 1 (
    echo Failed to install frontend dependencies
    pause
    exit /b
)

echo.
echo ============================================================
echo Installation Complete!
echo ============================================================
echo.
echo To start the system:
echo.
echo 1. Open Terminal 1 and run:
echo    cd backend
echo    python app.py
echo.
echo 2. Open Terminal 2 and run:
echo    cd frontend
echo    npm run dev
echo.
echo 3. Open browser and visit:
echo    http://localhost:3000
echo.
echo ============================================================
pause

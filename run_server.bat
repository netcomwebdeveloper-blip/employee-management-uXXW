@echo off
title NETCOM Employee Management Pro - Server Launcher
color 0B

echo ===============================================================
echo        NETCOM Employee Management Pro - Server Launcher
echo ===============================================================
echo.

cd /d "%~dp0"

if exist "..\venv\Scripts\activate.bat" (
    echo [*] Activating virtual environment...
    call "..\venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
    echo [*] Activating virtual environment...
    call "venv\Scripts\activate.bat"
)

echo [*] Checking database migrations...
python manage.py migrate

echo [*] Launching application in browser...
start http://127.0.0.1:8000/login/

echo [*] Starting Server on http://0.0.0.0:8000/ (Local and LAN Access)
echo [*] Press Ctrl+C to terminate the server.
echo.
python manage.py runserver 0.0.0.0:8000

pause

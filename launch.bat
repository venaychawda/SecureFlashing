@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ============================================================
echo   Secure Flashing Classic - One-Click Launch
echo ============================================================
echo.

REM -- 1. Pick a Python interpreter --------------------------------
REM     pydantic-core (a Rust/PyO3 extension pulled in by fastapi/pydantic)
REM     has no prebuilt wheel yet on very new Python releases (e.g. 3.13/3.14),
REM     which makes "pip install" try to compile it from source and fail.
REM     Prefer 3.12/3.11 via the "py" launcher when available; only fall
REM     back to plain "python" if no versioned launcher exists.
set "PYCMD="
where py >nul 2>nul
if not errorlevel 1 (
    py -3.12 -c "print(1)" >nul 2>nul
    if not errorlevel 1 set "PYCMD=py -3.12"
    if not defined PYCMD (
        py -3.11 -c "print(1)" >nul 2>nul
        if not errorlevel 1 set "PYCMD=py -3.11"
    )
)
if not defined PYCMD (
    where python >nul 2>nul
    if not errorlevel 1 set "PYCMD=python"
)
if not defined PYCMD (
    echo [ERROR] No Python interpreter was found - checked "py" launcher and "python" on PATH.
    echo         Install Python 3.11 or 3.12 from https://www.python.org/downloads/
    echo         and make sure "Add python.exe to PATH" is checked.
    pause
    exit /b 1
)
echo       Using interpreter: !PYCMD!

REM -- 2. Create virtual environment if missing ----------------------
if not exist "venv\Scripts\activate.bat" (
    echo [1/5] Creating virtual environment in .\venv ...
    !PYCMD! -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create the virtual environment.
        pause
        exit /b 1
    )
) else (
    echo [1/5] Virtual environment already exists - reusing .\venv
)

REM -- 3. Activate virtual environment --------------------------------
call "venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate the virtual environment.
    pause
    exit /b 1
)

REM -- 4. Install/refresh dependencies --------------------------------
echo [2/5] Installing Python dependencies from requirements.txt ...
python -m pip install --upgrade pip >nul 2>nul
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Dependency installation failed. See output above.
    echo         If the error mentions building "pydantic-core" ^(Rust/PyO3^),
    echo         your Python version is too new for the pinned pydantic wheel.
    echo         Delete the .\venv folder and rerun this script after installing
    echo         Python 3.11 or 3.12 alongside your current version.
    pause
    exit /b 1
)

REM -- 5. Warn (do not touch) if port 8000 is already occupied --------
echo [3/5] Checking whether port 8000 is free ...
set PORT_BUSY=0
for /f "tokens=1" %%L in ('netstat -ano ^| findstr /r /c:"127.0.0.1:8000 .*LISTENING" /c:"0.0.0.0:8000 .*LISTENING"') do set PORT_BUSY=1
if "!PORT_BUSY!"=="1" (
    echo.
    echo [WARNING] Port 8000 is already in use by another process on this
    echo           machine ^(possibly a different project's server^). This
    echo           script will NOT stop it. The backend below may fail to
    echo           bind, or the dashboard may end up talking to that other
    echo           service instead of this project's API.
    echo           Free port 8000 yourself first if that happens.
    echo.
)

REM -- 6. Start the FastAPI backend in its own window -----------------
echo [4/5] Starting FastAPI backend on http://localhost:8000 ...
start "Secure Flashing Classic - Backend (port 8000)" cmd /k "call venv\Scripts\activate.bat && uvicorn api.main:app --reload --port 8000"

REM Give uvicorn a few seconds to come up before opening the client.
REM Fully-qualified path avoids picking up a non-Windows "timeout" (e.g. from
REM Git for Windows / MSYS PATH entries) that doesn't understand /t syntax.
"%SystemRoot%\System32\timeout.exe" /t 4 /nobreak >nul

REM -- 7. Open the live monitor dashboard (the client) ----------------
echo [5/5] Opening docs\secure_flashing_classic_monitor.html ...
start "" "%~dp0docs\secure_flashing_classic_monitor.html"

echo.
echo ============================================================
echo   Backend is running in the separate "Backend" window.
echo   Dashboard opened in your default browser.
echo   Close the Backend window (or Ctrl+C in it) to stop the server.
echo ============================================================
echo.
pause
endlocal

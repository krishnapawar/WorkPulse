@echo off
title Today Work Update Manager
cd /d "%~dp0"

where py >nul 2>&1
if %errorlevel% equ 0 (
    set PY_CMD=py
) else (
    set PY_CMD=python
)

%PY_CMD% -c "import openpyxl" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing required dependencies (openpyxl)...
    %PY_CMD% -m pip install -r requirements.txt
)

%PY_CMD% app.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Application exited with an error.
    pause
)


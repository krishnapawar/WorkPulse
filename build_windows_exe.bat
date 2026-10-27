@echo off
rem ==============================================================================
rem WorkPulse - Windows Standalone Executable (.exe) Builder
rem Compiles Python, Tkinter, openpyxl, and all assets into dist\WorkPulse.exe
rem ==============================================================================
title WorkPulse - Windows Executable Builder
cd /d "%~dp0"

echo ==========================================================
echo  Building WorkPulse Standalone Windows Executable (.exe)
echo ==========================================================
echo.

rem 1. Detect Python / py launcher
where py >nul 2>&1
if %errorlevel% equ 0 (
    set PY_CMD=py
) else (
    where python >nul 2>&1
    if %errorlevel% equ 0 (
        set PY_CMD=python
    ) else (
        echo [ERROR] Python was not found in your PATH!
        echo Please install Python 3 (https://www.python.org/downloads/)
        echo Make sure to check "Add Python to PATH" during installation.
        pause
        exit /b 1
    )
)

echo [1/4] Checking Python environment...
%PY_CMD% --version

rem 2. Install / verify dependencies
echo.
echo [2/4] Verifying dependencies from requirements.txt...
%PY_CMD% -m pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies from requirements.txt.
    pause
    exit /b 1
)

rem 3. Install PyInstaller if missing
echo.
echo [3/4] Checking for PyInstaller...
%PY_CMD% -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing PyInstaller for Windows...
    %PY_CMD% -m pip install pyinstaller
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install PyInstaller.
        pause
        exit /b 1
    )
)

rem 4. Build the standalone executable
echo.
echo [4/4] Compiling WorkPulse.exe with PyInstaller...
echo This may take 1-2 minutes, please wait...
echo.

if exist "build" rmdir /s /q "build"
if exist "dist\WorkPulse.exe" del /f /q "dist\WorkPulse.exe"

set ICON_FLAG=
if exist "assets\icon.ico" (
    set ICON_FLAG=--icon "assets\icon.ico"
)

%PY_CMD% -m PyInstaller ^
    --noconsole ^
    --onefile ^
    --name "WorkPulse" ^
    %ICON_FLAG% ^
    --add-data "assets;assets" ^
    --add-data "settings.json;." ^
    --collect-data openpyxl ^
    app.py

if %errorlevel% equ 0 (
    echo.
    echo ==========================================================
    echo  Build Successful!
    echo ==========================================================
    echo.
    echo Standalone Windows Executable created at:
    echo   dist\WorkPulse.exe
    echo.
    echo You can distribute this single file to any Windows computer!
    echo No Python or pip installation required on target machines.
    echo.
) else (
    echo.
    echo [ERROR] PyInstaller build failed with exit code %errorlevel%.
)

pause

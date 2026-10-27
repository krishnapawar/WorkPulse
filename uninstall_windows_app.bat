@echo off
rem ==============================================================================
rem WorkPulse - Windows Shortcut Uninstaller
rem ==============================================================================
title WorkPulse - Uninstall Shortcuts
cd /d "%~dp0"

echo Removing WorkPulse Windows shortcuts...

if exist "%USERPROFILE%\Desktop\WorkPulse.lnk" (
    del /f /q "%USERPROFILE%\Desktop\WorkPulse.lnk"
    echo [OK] Removed Desktop shortcut.
)

if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\WorkPulse.lnk" (
    del /f /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\WorkPulse.lnk"
    echo [OK] Removed Start Menu shortcut.
)

echo.
echo WorkPulse shortcuts have been removed from your Windows Desktop and Start Menu.
pause

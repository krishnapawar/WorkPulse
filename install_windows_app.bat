@echo off
rem ==============================================================================
rem WorkPulse - 1-Click Windows Desktop & Start Menu Shortcut Installer
rem Creates Desktop & Start Menu shortcuts with custom WorkPulse icon
rem ==============================================================================
title WorkPulse - Windows App Shortcut Installer
cd /d "%~dp0"

echo ==========================================================
echo  Installing WorkPulse on Windows Desktop & Start Menu...
echo ==========================================================
echo.

set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
set "ICON_PATH=%PROJECT_DIR%\assets\icon.ico"
set "DESKTOP_DIR=%USERPROFILE%\Desktop"
set "STARTMENU_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs"

rem Determine target executable
if exist "%PROJECT_DIR%\dist\WorkPulse.exe" (
    set "TARGET_PATH=%PROJECT_DIR%\dist\WorkPulse.exe"
    set "TARGET_ARGS="
    echo [INFO] Found compiled executable at dist\WorkPulse.exe
) else (
    rem Detect pythonw.exe (runs GUI without a black command prompt window)
    where pythonw >nul 2>&1
    if %errorlevel% equ 0 (
        for /f "delims=" %%I in ('where pythonw') do set "TARGET_PATH=%%I"
        set "TARGET_ARGS=\"%PROJECT_DIR%\app.py\""
    ) else (
        where pyw >nul 2>&1
        if %errorlevel% equ 0 (
            for /f "delims=" %%I in ('where pyw') do set "TARGET_PATH=%%I"
            set "TARGET_ARGS=\"%PROJECT_DIR%\app.py\""
        ) else (
            set "TARGET_PATH=%PROJECT_DIR%\run.bat"
            set "TARGET_ARGS="
        )
    )
)

echo Target: %TARGET_PATH% %TARGET_ARGS%
echo Icon:   %ICON_PATH%
echo.

rem Use PowerShell to create Windows .lnk shortcuts
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ws = New-Object -ComObject WScript.Shell; " ^
    "$s1 = $ws.CreateShortcut('%DESKTOP_DIR%\WorkPulse.lnk'); " ^
    "$s1.TargetPath = '%TARGET_PATH%'; " ^
    "$s1.Arguments = '%TARGET_ARGS%'; " ^
    "$s1.WorkingDirectory = '%PROJECT_DIR%'; " ^
    "if (Test-Path '%ICON_PATH%') { $s1.IconLocation = '%ICON_PATH%,0' }; " ^
    "$s1.Description = 'WorkPulse - Daily Work Update Manager & Shift Tracker'; " ^
    "$s1.Save(); " ^
    "$s2 = $ws.CreateShortcut('%STARTMENU_DIR%\WorkPulse.lnk'); " ^
    "$s2.TargetPath = '%TARGET_PATH%'; " ^
    "$s2.Arguments = '%TARGET_ARGS%'; " ^
    "$s2.WorkingDirectory = '%PROJECT_DIR%'; " ^
    "if (Test-Path '%ICON_PATH%') { $s2.IconLocation = '%ICON_PATH%,0' }; " ^
    "$s2.Description = 'WorkPulse - Daily Work Update Manager & Shift Tracker'; " ^
    "$s2.Save();"

if %errorlevel% equ 0 (
    echo ==========================================================
    echo  WorkPulse has been installed successfully on Windows!
    echo ==========================================================
    echo.
    echo  Desktop Shortcut:     %DESKTOP_DIR%\WorkPulse.lnk
    echo  Start Menu Shortcut:  %STARTMENU_DIR%\WorkPulse.lnk
    echo.
    echo * Search 'WorkPulse' in your Windows Start Menu anytime.
    echo * Right-click the shortcut to 'Pin to Taskbar' for instant access!
    echo.
) else (
    echo [ERROR] Failed to create Windows shortcuts.
)

pause

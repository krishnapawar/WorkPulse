#!/usr/bin/env bash
# ==============================================================================
# WorkPulse - 1-Click Ubuntu / Debian Desktop Application Installer
# Integrates WorkPulse into Ubuntu Dash, App Menu, Dock, and Desktop Shortcuts
# ==============================================================================

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo "🚀 Installing WorkPulse on Ubuntu / Linux..."
echo "=========================================================="

# 1. Ensure run.sh is executable
chmod +x "$DIR/run.sh"

# 2. Check for dependencies (Python 3, tkinter, openpyxl)
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Error: Python 3 is not installed. Please run: sudo apt install python3"
    exit 1
fi

if ! python3 -c "import tkinter" >/dev/null 2>&1; then
    echo "⚠️  Tkinter is missing. Attempting to install via apt..."
    if command -v sudo >/dev/null 2>&1; then
        sudo apt-get update && sudo apt-get install -y python3-tk
    else
        echo "❌ Please install python3-tk manually: sudo apt install python3-tk"
        exit 1
    fi
fi

# Ensure openpyxl is installed
if ! python3 -c "import openpyxl" >/dev/null 2>&1; then
    echo "📦 Installing openpyxl..."
    python3 -m pip install -r requirements.txt --break-system-packages 2>/dev/null || python3 -m pip install -r requirements.txt
fi

# 3. Setup User Icons Directory
ICONS_DIR="$HOME/.local/share/icons/hicolor/512x512/apps"
mkdir -p "$ICONS_DIR"
if [ -f "$DIR/assets/icon.png" ]; then
    cp "$DIR/assets/icon.png" "$ICONS_DIR/workpulse.png"
    ICON_PATH="$ICONS_DIR/workpulse.png"
else
    ICON_PATH="$DIR/assets/icon.png"
fi

# 4. Create Desktop Entry in Applications Menu (~/.local/share/applications)
APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPS_DIR"

DESKTOP_FILE="$APPS_DIR/workpulse.desktop"

cat <<EOF > "$DESKTOP_FILE"
[Desktop Entry]
Version=1.0
Type=Application
Name=WorkPulse
GenericName=Work Update Manager
Comment=Desktop work update logger, shift tracker, and team standup generator
Exec=$DIR/run.sh
Icon=$ICON_PATH
Path=$DIR
Terminal=false
StartupNotify=true
StartupWMClass=app.py
Categories=Office;ProjectManagement;
Keywords=work;update;pulse;tasks;shift;timesheet;logger;excel;
Actions=OpenExcel;

[Desktop Action OpenExcel]
Name=Open Excel Data File
Exec=xdg-open $DIR/data.xlsx
EOF

chmod +x "$DESKTOP_FILE"

# 5. Optionally create Desktop shortcut on ~/Desktop if directory exists
if [ -d "$HOME/Desktop" ]; then
    cp "$DESKTOP_FILE" "$HOME/Desktop/workpulse.desktop"
    chmod +x "$HOME/Desktop/workpulse.desktop"
    # Allow launching on GNOME desktop
    if command -v gio >/dev/null 2>&1; then
        gio set "$HOME/Desktop/workpulse.desktop" metadata::trusted true 2>/dev/null || true
    fi
    echo "📌 Created Desktop shortcut: $HOME/Desktop/workpulse.desktop"
fi

# 6. Update Desktop Database & Icon Cache
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
fi

echo ""
echo "=========================================================="
echo "✅ WorkPulse has been successfully installed on Ubuntu!"
echo "=========================================================="
echo "• Search 'WorkPulse' in your Ubuntu Applications Dash / App Menu"
echo "• Right-click the app icon to 'Add to Favorites' / Pin to Ubuntu Dock"
echo "• Launch anytime with a single click!"
echo ""

#!/usr/bin/env bash
# ==============================================================================
# WorkPulse - Ubuntu Application Uninstaller
# ==============================================================================

set -e

echo "Removing WorkPulse desktop shortcuts and icons..."

rm -f "$HOME/.local/share/applications/workpulse.desktop"
rm -f "$HOME/Desktop/workpulse.desktop"
rm -f "$HOME/.local/share/icons/hicolor/512x512/apps/workpulse.png"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
fi

echo "✅ WorkPulse application launcher removed from Ubuntu App Menu and Desktop."

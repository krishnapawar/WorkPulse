#!/usr/bin/env bash
# ==============================================================================
# WorkPulse - Mobile Phone Simulator Launcher for Desktop
# Runs the mobile app in an interactive phone-sized window on your PC screen
# ==============================================================================

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo "📱 Launching WorkPulse Mobile Simulator on Desktop..."
echo "=========================================================="
echo "Aspect Ratio: 412x850 (Android Phone Dimensions)"
echo "Press Ctrl+C or close the window to exit."
echo ""

python3 mobile_app.py


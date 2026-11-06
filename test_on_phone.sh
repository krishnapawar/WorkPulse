#!/usr/bin/env bash
# ==============================================================================
# WorkPulse - Phone Test & Install Assistant (USB Cable & Wi-Fi)
# ==============================================================================

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Locate adb
export PATH="$HOME/.local/bin:$HOME/.buildozer/android/platform/android-sdk/platform-tools:$PATH"
ADB_BIN="$(command -v adb 2>/dev/null || echo "/home/kali/.local/bin/adb")"

APK_PATH="${DIR}/dist/workpulse.apk"
PKG_NAME="org.krishnapawar.workpulse"

if [ ! -f "$APK_PATH" ]; then
    echo "❌ Error: APK not found at dist/workpulse.apk"
    echo "Run ./build_apk.sh first."
    exit 1
fi

clear
echo "=========================================================="
echo "📱 WorkPulse Mobile Testing Assistant"
echo "=========================================================="
echo "Choose how you want to connect your phone:"
echo ""
echo "  [1] 🔌 USB Cable (Direct ADB Install & Test)"
echo "  [2] 📶 Wi-Fi Wireless ADB (Install wirelessly over Wi-Fi)"
echo "  [3] 🌐 Wi-Fi Instant Browser Download (No ADB needed, via Phone Browser)"
echo "  [4] 📜 View Live Mobile App Logs (adb logcat python)"
echo "  [5] 🚀 Launch WorkPulse App on Phone"
echo "  [0] Exit"
echo "=========================================================="
read -p "Select an option [1-5]: " choice

case "$choice" in
    1)
        echo ""
        echo "🔌 Checking USB Connection..."
        "$ADB_BIN" devices
        echo ""
        echo "💡 If your phone is not showing above:"
        echo "   1. On your phone, go to Settings -> Developer Options -> Enable 'USB Debugging'"
        echo "   2. Plug in your USB cable and select 'File Transfer' mode"
        echo "   3. Look at your phone screen and tap 'Always allow from this computer'"
        echo ""
        read -p "Press Enter to install APK on your phone... "
        echo ""
        echo "📦 Installing WorkPulse on your phone..."
        "$ADB_BIN" install -r "$APK_PATH"
        if [ $? -eq 0 ]; then
            echo ""
            echo "✅ Installation SUCCESSFUL!"
            echo "🚀 Launching WorkPulse on your phone..."
            "$ADB_BIN" shell monkey -p "$PKG_NAME" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1 || true
            echo ""
            read -p "Do you want to view live logs? (y/n): " show_logs
            if [[ "$show_logs" =~ ^[Yy]$ ]]; then
                echo "📜 Streaming Python logs from phone (Ctrl+C to stop)..."
                "$ADB_BIN" logcat -s python:D WorkPulse:D
            fi
        else
            echo "❌ Installation failed. Please check phone prompt and USB cable."
        fi
        ;;

    2)
        echo ""
        echo "📶 Wireless ADB Setup (Phone & PC must be on SAME Wi-Fi network)"
        echo "PC IP: $(hostname -I | awk '{print $1}')"
        echo ""
        echo "On your Android Phone (Android 11+):"
        echo "1. Go to Settings -> Developer Options -> Enable 'Wireless Debugging'"
        echo "2. Tap on 'Wireless Debugging' -> Tap 'Pair device with pairing code'"
        echo "   (You will see: IP address, Port, and a 6-digit Wi-Fi pairing code)"
        echo ""
        read -p "Did you open the Wireless Pairing screen on phone? (y/n): " paired_ready
        if [[ "$paired_ready" =~ ^[Yy]$ ]]; then
            read -p "Enter Phone IP and Port shown on screen (e.g. 192.168.1.15:41234): " phone_addr
            read -p "Enter the 6-digit pairing code: " pair_code
            echo "Pairing with phone..."
            "$ADB_BIN" pair "$phone_addr" "$pair_code"
            
            echo ""
            echo "Now look at the main 'Wireless Debugging' screen on your phone:"
            read -p "Enter the IP and Port from the main screen (e.g. 192.168.1.15:37890): " connect_addr
            "$ADB_BIN" connect "$connect_addr"
            
            echo ""
            echo "Connected devices:"
            "$ADB_BIN" devices
            
            echo ""
            echo "📦 Installing WorkPulse wirelessly..."
            "$ADB_BIN" install -r "$APK_PATH"
            echo "✅ Wireless Install Complete!"
            "$ADB_BIN" shell monkey -p "$PKG_NAME" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1 || true
        fi
        ;;

    3)
        HOST_IP="$(hostname -I | awk '{print $1}')"
        echo ""
        echo "🌐 Wi-Fi Instant Browser Download (Zero setup required!)"
        echo "----------------------------------------------------------"
        echo "1. Make sure your phone is connected to the same Wi-Fi router."
        echo "2. Open Google Chrome (or any browser) on your phone."
        echo "3. Type this URL in your phone's browser:"
        echo ""
        echo "   👉 http://${HOST_IP}:8080/workpulse.apk"
        echo ""
        echo "4. Tap 'Download anyway' and tap the file to install!"
        echo "----------------------------------------------------------"
        echo "Starting temporary web server on port 8080 (Press Ctrl+C to stop)..."
        cd "${DIR}/dist"
        python3 -m http.server 8080
        ;;

    4)
        echo ""
        echo "📜 Streaming live Python logs from phone (Ctrl+C to stop)..."
        "$ADB_BIN" logcat -c
        "$ADB_BIN" logcat -s python:D WorkPulse:D
        ;;

    5)
        echo "🚀 Launching WorkPulse..."
        "$ADB_BIN" shell monkey -p "$PKG_NAME" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1 || true
        ;;

    0)
        echo "Goodbye!"
        exit 0
        ;;
    *)
        echo "Invalid selection."
        ;;
esac


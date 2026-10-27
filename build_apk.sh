#!/usr/bin/env bash
# ==============================================================================
# WorkPulse - Android APK Builder (Local Buildozer)
# Builds workpulse.apk for Android phones & tablets
# ==============================================================================

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo "🤖 Building WorkPulse Android APK..."
echo "=========================================================="

# 1. Check Python 3
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Error: Python 3 is not installed."
    exit 1
fi

# 2. Virtual Environment Setup (avoids PEP 668 externally-managed-environment error)
VENV_DIR="${DIR}/.venv_buildozer"
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating isolated Python virtual environment for Buildozer at ${VENV_DIR}..."
    python3 -m venv "$VENV_DIR"
fi

source "${VENV_DIR}/bin/activate"

# 3. Check / Install Buildozer inside virtual environment
if ! python3 -c "import buildozer" >/dev/null 2>&1; then
    echo "📦 Installing Buildozer and Cython in isolated virtual environment..."
    pip install --upgrade pip
    pip install Cython buildozer
fi

# 4. Check Java (OpenJDK)
if ! command -v javac >/dev/null 2>&1; then
    echo ""
    echo "⚠️  Java JDK is required for Android build."
    echo "Attempting to install default-jdk and build tools..."
    if command -v sudo >/dev/null 2>&1; then
        # Detect available JDK package in Debian/Kali
        JDK_PKG="default-jdk"
        if ! apt-cache show default-jdk >/dev/null 2>&1; then
            if apt-cache show openjdk-21-jdk >/dev/null 2>&1; then
                JDK_PKG="openjdk-21-jdk"
            elif apt-cache show openjdk-17-jdk >/dev/null 2>&1; then
                JDK_PKG="openjdk-17-jdk"
            fi
        fi

        echo "📦 Installing ${JDK_PKG} and build dependencies..."
        sudo apt-get install -y "$JDK_PKG" autoconf libtool pkg-config zlib1g-dev libncurses-dev cmake libffi-dev libssl-dev zip unzip || {
            echo "⚠️ Trying apt update and reinstalling..."
            sudo apt-get update || true
            sudo apt-get install -y "$JDK_PKG" autoconf libtool pkg-config zlib1g-dev libncurses-dev cmake libffi-dev libssl-dev zip unzip || {
                echo ""
                echo "❌ Failed to install Java JDK via apt."
                echo "💡 TIP: Your Kali mirror may be syncing or packages need manual install:"
                echo "   sudo apt install -y default-jdk"
                echo "   OR use GitHub Actions to build the APK completely in the cloud with zero setup!"
                exit 1
            }
        }
    else
        echo "❌ Sudo not available. Please install Java JDK: sudo apt install -y default-jdk"
        exit 1
    fi
fi

# 4. Run Buildozer build
echo ""
echo "🚀 Running Buildozer (downloading Android SDK/NDK and compiling APK)..."
echo "Note: The first build will take 10-15 minutes to download Android toolchains."
echo ""

yes | buildozer android debug

echo ""
echo "=========================================================="
echo "🎉 Android APK Build Complete!"
echo "APK files generated in: ${DIR}/dist/"
ls -lh "${DIR}/dist/"*.apk 2>/dev/null || true
echo "=========================================================="
echo "To install on your Android phone:"
echo "1. Enable 'Developer Options' and 'USB Debugging' on your phone."
echo "2. Connect phone via USB and run: adb install dist/*.apk"
echo "   Or send the .apk file to your phone via WhatsApp/Drive/USB and tap to install!"
echo ""

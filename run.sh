#!/usr/bin/env bash
# Launch script for Today Work Update Manager on macOS and Linux
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Check Python 3
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "❌ Error: Python 3 is not installed or not in your PATH."
    echo "Please install Python 3 (https://www.python.org/downloads/)."
    exit 1
fi

# Check openpyxl dependency
if ! $PYTHON_CMD -c "import openpyxl" >/dev/null 2>&1; then
    echo "📦 Installing required dependencies from requirements.txt..."
    $PYTHON_CMD -m pip install -r requirements.txt
fi

echo "🚀 Starting Today Work Update Manager..."
$PYTHON_CMD app.py

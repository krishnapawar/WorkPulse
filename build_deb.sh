#!/usr/bin/env bash
# ==============================================================================
# WorkPulse - Ubuntu / Debian .deb Package Builder
# Builds a standard installable .deb package for Ubuntu/Debian distributions
# ==============================================================================

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

VERSION="1.0.0"
PKG_NAME="workpulse"
PKG_DIR="${DIR}/build_deb_pkg"
DIST_DIR="${DIR}/dist"

echo "=========================================================="
echo "📦 Building WorkPulse .deb Package (v${VERSION})..."
echo "=========================================================="

rm -rf "$PKG_DIR"
mkdir -p "$PKG_DIR/DEBIAN"
mkdir -p "$PKG_DIR/opt/workpulse"
mkdir -p "$PKG_DIR/usr/bin"
mkdir -p "$PKG_DIR/usr/share/applications"
mkdir -p "$PKG_DIR/usr/share/icons/hicolor/512x512/apps"
mkdir -p "$PKG_DIR/usr/share/icons/hicolor/128x128/apps"
mkdir -p "$DIST_DIR"

# 1. DEBIAN/control file
cat <<EOF > "$PKG_DIR/DEBIAN/control"
Package: ${PKG_NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: all
Depends: python3, python3-tk, python3-openpyxl | python3-pip
Maintainer: WorkPulse Team <support@workpulse.local>
Description: Desktop work update logger, shift tracker, and team standup generator
 WorkPulse is a feature-packed desktop work update manager, shift tracker,
 and LAN team collaboration tool built with Python & Tkinter. It automatically
 logs tasks into month-wise Excel sheets, computes net working hours minus breaks,
 and syncs to team webhooks / REST APIs.
EOF

# 2. Copy application source files
cp "$DIR/app.py" "$PKG_DIR/opt/workpulse/"
cp "$DIR/lan_chat.py" "$PKG_DIR/opt/workpulse/"
cp "$DIR/requirements.txt" "$PKG_DIR/opt/workpulse/"
cp "$DIR/settings.json" "$PKG_DIR/opt/workpulse/"
cp -r "$DIR/assets" "$PKG_DIR/opt/workpulse/"

# 3. Create opt launcher wrapper
cat <<'EOF' > "$PKG_DIR/opt/workpulse/workpulse-launcher.sh"
#!/usr/bin/env bash
set -e

APP_DATA="$HOME/.workpulse"
mkdir -p "$APP_DATA"

# Seed default data.xlsx & settings if not present
if [ ! -f "$APP_DATA/settings.json" ]; then
    cp /opt/workpulse/settings.json "$APP_DATA/settings.json" 2>/dev/null || true
fi

cd "$APP_DATA"
exec python3 /opt/workpulse/app.py "$@"
EOF

chmod +x "$PKG_DIR/opt/workpulse/workpulse-launcher.sh"

# 4. /usr/bin command symlink
ln -sf /opt/workpulse/workpulse-launcher.sh "$PKG_DIR/usr/bin/workpulse"

# 5. Desktop Entry
cat <<EOF > "$PKG_DIR/usr/share/applications/workpulse.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=WorkPulse
GenericName=Work Update Manager
Comment=Desktop work update logger, shift tracker, and team standup generator
Exec=/usr/bin/workpulse
Icon=workpulse
Terminal=false
StartupNotify=true
StartupWMClass=app.py
Categories=Office;ProjectManagement;
Keywords=work;update;pulse;tasks;shift;timesheet;logger;excel;
EOF

# 6. Icons
if [ -f "$DIR/assets/icon.png" ]; then
    cp "$DIR/assets/icon.png" "$PKG_DIR/usr/share/icons/hicolor/512x512/apps/workpulse.png"
fi
if [ -f "$DIR/assets/icon_128.png" ]; then
    cp "$DIR/assets/icon_128.png" "$PKG_DIR/usr/share/icons/hicolor/128x128/apps/workpulse.png"
fi

# 7. Build .deb package using dpkg-deb
DEB_FILE="${DIST_DIR}/${PKG_NAME}_${VERSION}_all.deb"
dpkg-deb --build --root-owner-group "$PKG_DIR" "$DEB_FILE"

# Clean up temporary build tree
rm -rf "$PKG_DIR"

echo ""
echo "=========================================================="
echo "🎉 Build Complete!"
echo "Package generated at: $DEB_FILE"
echo "=========================================================="
echo "To install on any Ubuntu / Debian computer, simply run:"
echo "  sudo dpkg -i $DEB_FILE"
echo "Or double-click the .deb file in Ubuntu Files to open with Software Center."
echo ""

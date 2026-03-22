#!/usr/bin/env bash
# Easy Photo Print LX — Uninstaller

APP_ID="io.github.osmanksonmez.EasyPhotoPrintLX"
BINARY_NAME="easy-photo-print-lx"
SCRIPT_NAME="Print Photos…"

if [[ $EUID -eq 0 ]]; then
    PREFIX="/usr/local"
    APPS_DIR="/usr/share/applications"
    ICONS_DIR="/usr/share/icons/hicolor"
else
    PREFIX="$HOME/.local"
    APPS_DIR="$HOME/.local/share/applications"
    ICONS_DIR="$HOME/.local/share/icons/hicolor"
fi

echo ""
echo "  Uninstalling Easy Photo Print LX…"

rm -f "$PREFIX/bin/$BINARY_NAME"
rm -f "$APPS_DIR/$APP_ID.desktop"
rm -f "$HOME/.local/share/nautilus/scripts/$SCRIPT_NAME"
find "$ICONS_DIR" -name "$APP_ID.*" -delete 2>/dev/null || true

gtk-update-icon-cache -f -t "$ICONS_DIR" 2>/dev/null || true
update-desktop-database "$APPS_DIR" 2>/dev/null || true

echo "  ✓  Done."
echo ""

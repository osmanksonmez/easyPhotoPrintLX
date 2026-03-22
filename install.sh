#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  Easy Photo Print LX — Installer
#  Registers "Print Photos…" as a right-click action in Nautilus (Files)
# ─────────────────────────────────────────────────────────────────────────────

set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_SCRIPT="$APP_DIR/photo_print_app.py"

NAUTILUS_SCRIPTS="$HOME/.local/share/nautilus/scripts"
SCRIPT_NAME="Print Photos…"

echo ""
echo "  Easy Photo Print LX — Installer"
echo "  ────────────────────────────────────────"

# ── 1. Check Python & Pillow ─────────────────────────────────────────────────
echo ""
echo "  Checking dependencies…"

if ! command -v python3 &>/dev/null; then
    echo "  ✗  python3 not found. Install it with: sudo apt install python3"
    exit 1
fi

if ! python3 -c "from PIL import Image" &>/dev/null; then
    echo "  Installing Pillow…"
    python3 -m pip install Pillow --break-system-packages
fi

echo "  ✓  Python + Pillow OK"

# ── 2. Create Nautilus Scripts directory ─────────────────────────────────────
mkdir -p "$NAUTILUS_SCRIPTS"

# ── 3. Write the Nautilus script ─────────────────────────────────────────────
SCRIPT_PATH="$NAUTILUS_SCRIPTS/$SCRIPT_NAME"

cat > "$SCRIPT_PATH" <<NAUTILUSEOF
#!/usr/bin/env bash
# Easy Photo Print LX — Nautilus right-click script
# Reads selected file paths from the Nautilus env variable.

APP="$APP_SCRIPT"

if [ -n "\$NAUTILUS_SCRIPT_SELECTED_FILE_PATHS" ]; then
    # mapfile reads every newline-separated path into an array element
    # (IFS=\$'\\n' read -ra only captures the first line -- don't use that)
    mapfile -t FILES <<< "\$NAUTILUS_SCRIPT_SELECTED_FILE_PATHS"
    python3 "\$APP" "\${FILES[@]}"
else
    python3 "\$APP"
fi
NAUTILUSEOF

chmod +x "$SCRIPT_PATH"
echo "  ✓  Nautilus script installed: $SCRIPT_PATH"

# ── 4. Also create a .desktop launcher ───────────────────────────────────────
APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPS_DIR"

cat > "$APPS_DIR/photo-print.desktop" <<DESKEOF
[Desktop Entry]
Name=Easy Photo Print LX
Comment=Easy photo printing with layout options for Linux
Exec=python3 "$APP_SCRIPT" %F
Icon=document-print
Terminal=false
Type=Application
Categories=Graphics;Photography;
MimeType=image/jpeg;image/png;image/bmp;image/tiff;image/webp;image/gif;
StartupNotify=false
DESKEOF

chmod +x "$APPS_DIR/photo-print.desktop"
update-desktop-database "$APPS_DIR" 2>/dev/null || true
echo "  ✓  Desktop launcher installed"

# ── 5. Done ───────────────────────────────────────────────────────────────────
echo ""
echo "  ✓  Installation complete!"
echo ""
echo "  HOW TO USE:"
echo "  ──────────────────────────────────────────────────────────────"
echo "  Right-click: Open Nautilus (Files), select photo(s),"
echo "               right-click → Scripts → 'Print Photos…'"
echo ""
echo "  Direct:      python3 \"$APP_SCRIPT\" photo.jpg photo2.jpg"
echo ""
echo "  No args:     python3 \"$APP_SCRIPT\""
echo "               (opens a file picker)"
echo "  ──────────────────────────────────────────────────────────────"
echo ""

# Restart Nautilus to pick up the new script (silently)
if pgrep -x nautilus &>/dev/null; then
    nautilus -q 2>/dev/null || true
    echo "  (Nautilus restarted to load the new script)"
    echo ""
fi

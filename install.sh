#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  Easy Photo Print LX — Installer
#  Installs as a proper desktop application + Nautilus right-click script
#
#  Usage:
#    bash install.sh          # install for current user (~/.local)
#    sudo bash install.sh     # install system-wide (/usr/local)
# ─────────────────────────────────────────────────────────────────────────────

set -e

APP_ID="io.github.osmanksonmez.EasyPhotoPrintLX"
APP_NAME="Easy Photo Print LX"
BINARY_NAME="easy-photo-print-lx"
SCRIPT_NAME="Print Photos…"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_SCRIPT="$REPO_DIR/photo_print_app.py"
ICON_SRC="$REPO_DIR/icon.svg"

# ── Decide install prefix ─────────────────────────────────────────────────────
if [[ $EUID -eq 0 ]]; then
    PREFIX="/usr/local"
    APPS_DIR="/usr/share/applications"
    ICONS_DIR="/usr/share/icons/hicolor"
    echo ""
    echo "  Installing system-wide to $PREFIX"
else
    PREFIX="$HOME/.local"
    APPS_DIR="$HOME/.local/share/applications"
    ICONS_DIR="$HOME/.local/share/icons/hicolor"
    echo ""
    echo "  Installing for current user to $PREFIX"
fi

BIN_DIR="$PREFIX/bin"

echo "  ────────────────────────────────────────────"

# ── 1. Check Python & install Pillow ─────────────────────────────────────────
echo ""
echo "  Checking dependencies…"

if ! command -v python3 &>/dev/null; then
    echo "  ✗  python3 not found.  sudo apt install python3"
    exit 1
fi

if ! python3 -c "from PIL import Image" &>/dev/null; then
    echo "  Installing Pillow…"
    python3 -m pip install Pillow --break-system-packages --quiet \
        || python3 -m pip install Pillow --user --quiet
fi

echo "  ✓  Python $(python3 --version | cut -d' ' -f2) + Pillow OK"

# ── 2. Install the launcher binary ───────────────────────────────────────────
echo ""
echo "  Installing application…"

mkdir -p "$BIN_DIR"
LAUNCHER="$BIN_DIR/$BINARY_NAME"

# Write a launcher wrapper (not a symlink) so the binary name is clean
cat > "$LAUNCHER" << LAUNCHEOF
#!/usr/bin/env bash
exec python3 "$APP_SCRIPT" "\$@"
LAUNCHEOF
chmod +x "$LAUNCHER"
echo "  ✓  Launcher: $LAUNCHER"

# ── 3. Install icon ───────────────────────────────────────────────────────────
for SIZE in 16 32 48 64 128 256 scalable; do
    if [[ "$SIZE" == "scalable" ]]; then
        ICON_DIR="$ICONS_DIR/scalable/apps"
        ICON_PATH="$ICON_DIR/$APP_ID.svg"
        mkdir -p "$ICON_DIR"
        cp "$ICON_SRC" "$ICON_PATH"
    else
        ICON_DIR="$ICONS_DIR/${SIZE}x${SIZE}/apps"
        ICON_PATH="$ICON_DIR/$APP_ID.png"
        mkdir -p "$ICON_DIR"
        # Convert SVG to PNG using Python/Pillow (cairosvg if available, else copy SVG)
        if python3 -c "import cairosvg" &>/dev/null; then
            python3 -c "
import cairosvg
cairosvg.svg2png(url='$ICON_SRC', write_to='$ICON_PATH', output_width=$SIZE, output_height=$SIZE)
"
        fi
    fi
done
echo "  ✓  Icon installed ($APP_ID)"

# ── 4. Install .desktop entry ─────────────────────────────────────────────────
mkdir -p "$APPS_DIR"
DESKTOP_PATH="$APPS_DIR/$APP_ID.desktop"

cat > "$DESKTOP_PATH" << DESKEOF
[Desktop Entry]
Version=1.0
Type=Application
Name=$APP_NAME
Comment=Print photos with flexible layout options — right-click or open directly
Exec=$LAUNCHER %F
Icon=$APP_ID
Terminal=false
Categories=Graphics;Photography;
MimeType=image/jpeg;image/png;image/bmp;image/tiff;image/webp;image/gif;image/heic;
StartupNotify=false
Keywords=print;photo;picture;layout;
DESKEOF

chmod +x "$DESKTOP_PATH"

# Refresh icon cache and desktop database
gtk-update-icon-cache -f -t "$ICONS_DIR" 2>/dev/null || true
update-desktop-database "$APPS_DIR" 2>/dev/null || true
echo "  ✓  Desktop entry: $DESKTOP_PATH"

# ── 5. Install Nautilus right-click script ────────────────────────────────────
NAUTILUS_SCRIPTS="$HOME/.local/share/nautilus/scripts"
mkdir -p "$NAUTILUS_SCRIPTS"
NAUTILUS_SCRIPT="$NAUTILUS_SCRIPTS/$SCRIPT_NAME"

cat > "$NAUTILUS_SCRIPT" << 'NAUTILUSEOF'
#!/usr/bin/env bash
# Easy Photo Print LX — Nautilus right-click script
BINARY="easy-photo-print-lx"

# Prefer installed binary; fall back to PATH
if command -v "$BINARY" &>/dev/null; then
    CMD="$BINARY"
else
    echo "easy-photo-print-lx not found. Run install.sh first." >&2
    exit 1
fi

if [ -n "$NAUTILUS_SCRIPT_SELECTED_FILE_PATHS" ]; then
    mapfile -t FILES <<< "$NAUTILUS_SCRIPT_SELECTED_FILE_PATHS"
    "$CMD" "${FILES[@]}"
else
    "$CMD"
fi
NAUTILUSEOF

chmod +x "$NAUTILUS_SCRIPT"
echo "  ✓  Nautilus script: $NAUTILUS_SCRIPT"

# Restart Nautilus to pick up the new script
if pgrep -x nautilus &>/dev/null; then
    nautilus -q 2>/dev/null || true
fi

# ── 6. Done ───────────────────────────────────────────────────────────────────
echo ""
echo "  ✓  $APP_NAME installed!"
echo ""
echo "  HOW TO USE:"
echo "  ──────────────────────────────────────────────────────────────"
echo "  App menu:    Search for \"$APP_NAME\""
echo "  Right-click: Select photos in Nautilus → Scripts → \"$SCRIPT_NAME\""
echo "  Terminal:    $BINARY_NAME photo.jpg photo2.jpg"
echo "  ──────────────────────────────────────────────────────────────"
echo ""
echo "  To uninstall, run:  bash uninstall.sh"
echo ""

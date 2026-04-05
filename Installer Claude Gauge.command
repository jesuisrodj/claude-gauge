#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#   Claude Gauge — Installeur
#   Double-cliquez pour installer.
# ═══════════════════════════════════════════════════════════════

clear
echo ""
echo "  +---------------------------------------------------+"
echo "  |                                                   |"
echo "  |       Claude Gauge — Installation                 |"
echo "  |                                                   |"
echo "  |   Affiche l'usage de votre forfait Claude         |"
echo "  |   dans la barre de menu macOS.                    |"
echo "  |                                                   |"
echo "  +---------------------------------------------------+"
echo ""

ok()   { echo "  [OK] $1"; }
info() { echo "  [..] $1"; }
fail() { echo "  [!!] $1"; echo ""; read -n1 -p "  Appuyez sur une touche..."; exit 1; }
step() { echo ""; echo "  > $1..."; }

INSTALL_DIR="$HOME/.claude-gauge"
APP_FILE="$INSTALL_DIR/claude_menubar.py"
PLIST_LABEL="com.claude.gauge"
PLIST_FILE="$HOME/Library/LaunchAgents/$PLIST_LABEL.plist"

# ─── Python 3 ─────────────────────────────────────────────────

step "Python 3"

if command -v python3 &>/dev/null; then
    PYTHON="$(command -v python3)"
    ok "$(python3 --version 2>&1)"
else
    info "Python 3 non trouve, installation via Xcode CLI Tools..."
    xcode-select --install 2>/dev/null
    echo "  Relancez cet installeur apres l'installation."
    read -n1 -p "  Appuyez sur une touche..."; exit 0
fi

# ─── rumps ────────────────────────────────────────────────────

step "Dependances"

if $PYTHON -c "import rumps" 2>/dev/null; then
    ok "rumps OK"
else
    $PYTHON -m pip install rumps --quiet --break-system-packages 2>/dev/null || \
    $PYTHON -m pip install rumps --quiet --user 2>/dev/null || \
    $PYTHON -m pip install rumps --quiet 2>/dev/null
    $PYTHON -c "import rumps" 2>/dev/null && ok "rumps installe" || fail "Echec pip install rumps"
fi

# ─── Copie ────────────────────────────────────────────────────

step "Installation"

mkdir -p "$INSTALL_DIR"
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ ! -f "$SOURCE_DIR/claude_menubar.py" ]; then
    fail "claude_menubar.py introuvable"
fi

cp "$SOURCE_DIR/claude_menubar.py" "$APP_FILE"
chmod +x "$APP_FILE"
ok "Installe dans ~/.claude-gauge/"

# ─── LaunchAgent ──────────────────────────────────────────────

step "Demarrage automatique"

launchctl bootout "gui/$(id -u)/$PLIST_LABEL" 2>/dev/null
pkill -f "claude_menubar.py" 2>/dev/null
sleep 1

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST_FILE" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$APP_FILE</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>$INSTALL_DIR/gauge.log</string>
    <key>StandardErrorPath</key>
    <string>$INSTALL_DIR/gauge-error.log</string>
</dict>
</plist>
PLIST
ok "Configure"

# ─── Lancement ────────────────────────────────────────────────

step "Lancement"

launchctl bootstrap "gui/$(id -u)" "$PLIST_FILE" 2>/dev/null || \
launchctl load "$PLIST_FILE" 2>/dev/null
sleep 2

pgrep -f "claude_menubar.py" >/dev/null && ok "Claude Gauge tourne" || {
    nohup $PYTHON "$APP_FILE" &>/dev/null &
    sleep 2
    pgrep -f "claude_menubar.py" >/dev/null && ok "Claude Gauge tourne" || \
    info "Logs : cat ~/.claude-gauge/gauge-error.log"
}

# ─── Fin ──────────────────────────────────────────────────────

echo ""
echo "  +---------------------------------------------------+"
echo "  |                                                   |"
echo "  |   Installation terminee.                          |"
echo "  |                                                   |"
echo "  |   'Claude --' apparait dans la barre de menu.     |"
echo "  |   Cliquez dessus > 'Configurer la session...'     |"
echo "  |   pour entrer votre cle de session claude.ai      |"
echo "  |                                                   |"
echo "  +---------------------------------------------------+"
echo ""
read -n1 -p "  Appuyez sur une touche pour fermer..."

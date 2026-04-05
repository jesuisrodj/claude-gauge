#!/bin/bash
# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
#   Claude Gauge â Installeur distant
#   Usage : curl -sL https://raw.githubusercontent.com/jesuisrodj/claude-gauge/main/install.sh | bash
# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

set -e

clear
echo ""
echo "  +---------------------------------------------------+"
echo "  |                                                   |"
echo "  |       Claude Gauge â Installation                 |"
echo "  |                                                   |"
echo "  |   Affiche l'usage de votre forfait Claude         |"
echo "  |   dans la barre de menu macOS.                    |"
echo "  |                                                   |"
echo "  +---------------------------------------------------+"
echo ""

ok()   { echo "  [OK] $1"; }
info() { echo "  [..] $1"; }
fail() { echo "  [!!] $1"; exit 1; }
step() { echo ""; echo "  > $1..."; }

INSTALL_DIR="$HOME/.claude-gauge"
APP_FILE="$INSTALL_DIR/claude_menubar.py"
PLIST_LABEL="com.claude.gauge"
PLIST_FILE="$HOME/Library/LaunchAgents/$PLIST_LABEL.plist"
REPO_RAW="https://raw.githubusercontent.com/jesuisrodj/claude-gauge/main"

# âââ Python 3 âââââââââââââââââââââââââââââââââââââââââââââââââ

step "Verification de Python 3"

if command -v python3 &>/dev/null; then
    PYTHON="$(command -v python3)"
    ok "$(python3 --version 2>&1)"
else
    info "Python 3 non trouve, installation via Xcode CLI Tools..."
    xcode-select --install 2>/dev/null
    echo "  Relancez cette commande apres l'installation de Xcode CLI Tools."
    exit 0
fi

# âââ rumps ââââââââââââââââââââââââââââââââââââââââââââââââââââ

step "Installation des dependances"

if $PYTHON -c "import rumps" 2>/dev/null; then
    ok "rumps OK"
else
    $PYTHON -m pip install rumps --quiet --break-system-packages 2>/dev/null || \
    $PYTHON -m pip install rumps --quiet --user 2>/dev/null || \
    $PYTHON -m pip install rumps --quiet 2>/dev/null
    $PYTHON -c "import rumps" 2>/dev/null && ok "rumps installe" || fail "Echec pip install rumps"
fi

# âââ Telechargement âââââââââââââââââââââââââââââââââââââââââââ

step "Telechargement de Claude Gauge"

mkdir -p "$INSTALL_DIR"

curl -sL "$REPO_RAW/claude_menubar.py" -o "$APP_FILE" || fail "Echec du telechargement"
chmod +x "$APP_FILE"
ok "Installe dans ~/.claude-gauge/"

# âââ Arret ancien processus âââââââââââââââââââââââââââââââââââ

launchctl bootout "gui/$(id -u)/$PLIST_LABEL" 2>/dev/null || true
pkill -f "claude_menubar.py" 2>/dev/null || true
sleep 1

# âââ LaunchAgent ââââââââââââââââââââââââââââââââââââââââââââââ

step "Configuration du demarrage automatique"

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
ok "LaunchAgent configure"

# âââ Lancement ââââââââââââââââââââââââââââââââââââââââââââââââ

step "Lancement"

launchctl bootstrap "gui/$(id -u)" "$PLIST_FILE" 2>/dev/null || \
launchctl load "$PLIST_FILE" 2>/dev/null || true
sleep 2

if pgrep -f "claude_menubar.py" >/dev/null; then
    ok "Claude Gauge tourne"
else
    nohup $PYTHON "$APP_FILE" &>/dev/null &
    sleep 2
    if pgrep -f "claude_menubar.py" >/dev/null; then
        ok "Claude Gauge tourne"
    else
        info "Verifiez les logs : cat ~/.claude-gauge/gauge-error.log"
    fi
fi

# âââ Fin ââââââââââââââââââââââââââââââââââââââââââââââââââââââ

echo ""
echo "  +---------------------------------------------------+"
echo "  |                                                   |"
echo "  |   Installation terminee.                          |"
echo "  |                                                   |"
echo "  |   'Claude --' apparait dans la barre de menu.     |"
echo "  |   Cliquez dessus > Parametrage >                  |"
echo "  |   'Configurer la session...'                      |"
echo "  |   pour entrer votre cle de session claude.ai      |"
echo "  |                                                   |"
echo "  +---------------------------------------------------+"
echo ""

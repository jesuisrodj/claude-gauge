#!/usr/bin/env python3
"""
Claude Gauge â Affiche l'usage du forfait Claude dans la barre de menu macOS.
Reprend les infos de la page "Limites d'utilisation" de l'app Claude :
  - Pourcentage utilise
  - Temps avant reinitialisation
"""

import json
import os
import sys
import shutil
import sqlite3
import threading
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import rumps
except ImportError:
    os.system(f"{sys.executable} -m pip install rumps --quiet --break-system-packages 2>/dev/null || {sys.executable} -m pip install rumps --quiet")
    import rumps

from AppKit import (
    NSImage,
    NSColor,
    NSBezierPath,
    NSMakeSize,
)
import math


def create_claude_icon(size=16):
    """
    Dessine le logo Claude (sparkle/etoile a 4 branches)
    en monochrome template â macOS adapte au mode clair/sombre.
    """
    img = NSImage.alloc().initWithSize_(NSMakeSize(size, size))
    img.setTemplate_(True)
    img.lockFocus()

    cx, cy = size / 2.0, size / 2.0
    r_outer = size / 2.0 - 1.0
    r_inner = r_outer * 0.28

    path = NSBezierPath.bezierPath()
    points = 4
    for i in range(points * 2):
        angle = math.pi / 2 + (math.pi * i / points)
        r = r_outer if i % 2 == 0 else r_inner
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        if i == 0:
            path.moveToPoint_((x, y))
        else:
            path.lineToPoint_((x, y))
    path.closePath()

    NSColor.blackColor().setFill()
    path.fill()

    img.unlockFocus()
    return img

# âââ Configuration âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

CONFIG_DIR = Path.home() / ".claude-gauge"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "session_key": "",
    "refresh_interval_seconds": 120,
}


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    return DEFAULT_CONFIG.copy()


def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


# âââ Session key auto-detection ââââââââââââââââââââââââââââââââââââââââââââââ


def find_session_key_from_desktop_app():
    """
    Tente de lire le cookie sessionKey depuis le stockage local
    de l'app Claude Desktop (Electron / Chromium).
    """
    candidates = [
        Path.home() / "Library/Application Support/Claude/Default/Cookies",
        Path.home() / "Library/Application Support/Claude/Cookies",
        Path.home() / "Library/Application Support/com.anthropic.claude/Default/Cookies",
        Path.home() / "Library/Application Support/com.anthropic.claude/Cookies",
    ]
    for cookies_db in candidates:
        if not cookies_db.exists():
            continue
        try:
            # Copier pour eviter le lock
            tmp = CONFIG_DIR / "cookies_tmp.db"
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cookies_db, tmp)
            conn = sqlite3.connect(str(tmp))
            cursor = conn.execute(
                "SELECT value, encrypted_value FROM cookies "
                "WHERE host_key LIKE '%claude.ai%' AND name = 'sessionKey' "
                "ORDER BY last_access_utc DESC LIMIT 1"
            )
            row = cursor.fetchone()
            conn.close()
            tmp.unlink(missing_ok=True)
            if row:
                value, encrypted = row
                if value:
                    return value
                # Les cookies Electron sont souvent chiffres via Keychain
                # On ne peut pas les dechiffrer facilement, fallback manuel
        except Exception:
            continue
    return None


# âââ API claude.ai âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ


def claude_api_request(session_key, path):
    """Requete vers l'API interne claude.ai."""
    url = f"https://claude.ai/api/{path}"
    req = urllib.request.Request(url)
    req.add_header("Cookie", f"sessionKey={session_key}")
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "Claude-Gauge/1.0")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode()), dict(resp.headers)


def fetch_usage(session_key):
    """
    Recupere les infos d'usage du forfait Claude.
    Essaie plusieurs endpoints connus.
    Retourne un dict: {percent, reset_seconds, tier, org_name}
    """
    result = {
        "percent": None,
        "reset_seconds": None,
        "tier": None,
        "org_name": None,
    }

    # 1. Bootstrap pour obtenir l'org_id et potentiellement les rate limits
    try:
        data, headers = claude_api_request(session_key, "bootstrap")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise RuntimeError("Session expiree") from e
        raise RuntimeError(f"Erreur API ({e.code})") from e

    # Extraire org_id
    org_id = None
    orgs = data.get("account", {}).get("memberships", [])
    if orgs:
        org_id = orgs[0].get("organization", {}).get("uuid")
        result["org_name"] = orgs[0].get("organization", {}).get("name")

    # Verifier si les rate limits sont dans bootstrap
    rate_limit = data.get("rate_limit") or data.get("rateLimit")
    if rate_limit:
        result["percent"] = rate_limit.get("usage_percentage") or rate_limit.get("percent")
        result["reset_seconds"] = rate_limit.get("reset_seconds") or rate_limit.get("resetSeconds")
        result["tier"] = rate_limit.get("tier")

    # 2. Si pas dans bootstrap, essayer l'endpoint rate_limit direct
    if result["percent"] is None and org_id:
        for endpoint in [
            f"organizations/{org_id}/rate_limit",
            f"organizations/{org_id}/chat_conversations/rate_limit",
            f"organizations/{org_id}/settings/rate_limit",
            f"organizations/{org_id}/usage",
        ]:
            try:
                rl_data, rl_headers = claude_api_request(session_key, endpoint)
                # Chercher le pourcentage dans la reponse
                pct = (
                    rl_data.get("usage_percentage")
                    or rl_data.get("percent_used")
                    or rl_data.get("usage", {}).get("percent")
                    or rl_data.get("percentage")
                )
                if pct is not None:
                    if isinstance(pct, (int, float)) and pct <= 1:
                        pct = pct * 100  # 0.9 -> 90
                    result["percent"] = float(pct)
                    result["reset_seconds"] = (
                        rl_data.get("reset_seconds")
                        or rl_data.get("resetSeconds")
                        or rl_data.get("seconds_until_reset")
                        or rl_data.get("resetsAt")
                    )
                    result["tier"] = rl_data.get("tier") or rl_data.get("max_tier")
                    break
            except Exception:
                continue

    # 3. Dernier recours: lire les headers de rate limit
    if result["percent"] is None:
        rl_limit = headers.get("x-ratelimit-limit")
        rl_remaining = headers.get("x-ratelimit-remaining")
        rl_reset = headers.get("x-ratelimit-reset")
        if rl_limit and rl_remaining:
            try:
                limit = float(rl_limit)
                remaining = float(rl_remaining)
                if limit > 0:
                    result["percent"] = ((limit - remaining) / limit) * 100
            except ValueError:
                pass
        if rl_reset:
            try:
                reset_time = datetime.fromisoformat(rl_reset.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                result["reset_seconds"] = max(0, (reset_time - now).total_seconds())
            except Exception:
                pass

    return result


def format_reset_time(seconds):
    """Formatte les secondes en 'Xh Ym'."""
    if seconds is None:
        return None
    seconds = int(seconds)
    if seconds <= 0:
        return "maintenant"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h > 0:
        return f"{h}h {m:02d}min"
    return f"{m}min"


# âââ Application âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ


class ClaudeGaugeApp(rumps.App):
    def __init__(self):
        super().__init__("Claude Gauge", title=" --", icon=None, quit_button=None)

        self.config = load_config()
        self.usage = {}
        self.last_update = None
        self.error_msg = None

        self.percent_item = rumps.MenuItem("Utilisation : --")
        self.reset_item = rumps.MenuItem("Reinitialisation : --")
        self.tier_item = rumps.MenuItem("Forfait : --")
        self.updated_item = rumps.MenuItem("MAJ : --")
        self.status_item = rumps.MenuItem("En attente")

        # Sous-menu Parametrage
        self.settings_menu = rumps.MenuItem("Parametrage")
        self.btn_session = rumps.MenuItem("Configurer la session...", callback=self.on_set_session)
        self.btn_open = rumps.MenuItem("Ouvrir claude.ai", callback=self.on_open_claude)
        self.btn_uninstall = rumps.MenuItem("Desinstaller...", callback=self.on_uninstall)
        self.settings_menu.update([self.btn_session, self.btn_open, self.btn_uninstall])

        self.menu = [
            self.percent_item,
            self.reset_item,
            self.tier_item,
            None,
            self.updated_item,
            self.status_item,
            None,
            self.settings_menu,
            None,
            rumps.MenuItem("Quitter", callback=self.on_quit),
        ]

        interval = self.config["refresh_interval_seconds"]
        self.timer = rumps.Timer(self.auto_refresh, interval)
        self.timer.start()

        # Auto-detection de la session au premier lancement
        if not self.config.get("session_key"):
            self._try_auto_detect()

        self.refresh_data()

    def _try_auto_detect(self):
        key = find_session_key_from_desktop_app()
        if key:
            self.config["session_key"] = key
            save_config(self.config)

    def auto_refresh(self, _):
        self.refresh_data()

    def refresh_data(self):
        threading.Thread(target=self._fetch_and_update, daemon=True).start()

    def _fetch_and_update(self):
        session_key = self.config.get("session_key", "")
        if not session_key:
            self.error_msg = "Session non configuree"
            self._update_ui_no_session()
            return
        try:
            self.usage = fetch_usage(session_key)
            self.last_update = datetime.now()
            self.error_msg = None
        except RuntimeError as e:
            self.error_msg = str(e)
        except Exception as e:
            self.error_msg = str(e)[:50]
        self._update_ui()

    def _set_icon(self):
        """Place l'icone Claude dans la barre de menu."""
        try:
            icon = create_claude_icon()
            self._nsapp.nsstatusitem.button().setImage_(icon)
        except Exception:
            pass

    def _update_ui(self):
        if self.error_msg:
            self._set_icon()
            self.title = " [!]"
            self.status_item.title = f"Erreur : {self.error_msg[:50]}"
            return

        pct = self.usage.get("percent")
        reset_s = self.usage.get("reset_seconds")
        tier = self.usage.get("tier")
        reset_txt = format_reset_time(reset_s)

        # Barre de menu : icone Claude + pourcentage
        self._set_icon()
        if pct is not None:
            self.title = f" {pct:.0f}%"
        else:
            self.title = " --"

        # Menu deroulant
        self.percent_item.title = f"Utilisation : {pct:.0f}%" if pct is not None else "Utilisation : --"
        self.reset_item.title = f"Reinitialisation : {reset_txt}" if reset_txt else "Reinitialisation : --"
        self.tier_item.title = f"Forfait : Max ({tier})" if tier else "Forfait : --"

        if self.last_update:
            self.updated_item.title = f"MAJ : {self.last_update.strftime('%H:%M')}"

        self.status_item.title = "Connecte"

    def _update_ui_no_session(self):
        self._set_icon()
        self.title = " --"
        self.percent_item.title = "Utilisation : --"
        self.reset_item.title = "Reinitialisation : --"
        self.tier_item.title = "Forfait : --"
        self.status_item.title = "Configurez votre session"

    # âââ Actions âââââââââââââââââââââââââââââââââââââââââââââââââââââ

    def on_set_session(self, _):
        current = self.config.get("session_key", "")
        masked = f"{current[:8]}...{current[-4:]}" if len(current) > 12 else ""
        w = rumps.Window(
            (
                "Collez votre cle de session Claude.\n\n"
                "Pour la trouver :\n"
                "1. Ouvrez claude.ai dans votre navigateur\n"
                "2. Outils dev (F12) > Application > Cookies\n"
                "3. Copiez la valeur de 'sessionKey'"
            ),
            "Session Claude",
            default_text=masked,
            ok="OK",
            cancel="Annuler",
            dimensions=(400, 24),
        )
        r = w.run()
        if r.clicked:
            key = r.text.strip()
            if key and key != masked:
                self.config["session_key"] = key
                save_config(self.config)
                self.refresh_data()

    def on_open_claude(self, _):
        os.system("open https://claude.ai/settings")

    def on_uninstall(self, _):
        resp = rumps.alert(
            "Desinstaller Claude Gauge ?",
            "Supprime la jauge, le demarrage automatique et la configuration.",
            ok="Desinstaller",
            cancel="Annuler",
        )
        if resp == 1:
            plist = Path.home() / "Library/LaunchAgents/com.claude.gauge.plist"
            os.system('launchctl bootout "gui/$(id -u)/com.claude.gauge" 2>/dev/null')
            if plist.exists():
                plist.unlink()
            if CONFIG_DIR.exists():
                shutil.rmtree(CONFIG_DIR, ignore_errors=True)
            rumps.quit_application()

    def on_quit(self, _):
        rumps.quit_application()


if __name__ == "__main__":
    ClaudeGaugeApp().run()

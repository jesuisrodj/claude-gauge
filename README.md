# Claude Gauge

Affiche l'utilisation de votre forfait Claude directement dans la barre de menu macOS.

Reprend les infos de la page "Limites d'utilisation" de claude.ai :
- Pourcentage d'utilisation
- Temps avant reinitialisation
- Niveau du forfait (ex: Max 5x)

---

## Installation

Ouvrez le Terminal et collez cette commande :

\`\`\`bash
curl -sL https://raw.githubusercontent.com/jesuisrodj/claude-gauge/main/install.sh | bash
\`\`\`

C'est tout. L'installeur telecharge l'application, configure le demarrage automatique et lance la jauge.

---

## Configuration

Au premier lancement, cliquez sur l'icone Claude dans la barre de menu, puis :

**Parametrage > Configurer la session...**

Pour obtenir votre cle de session :
1. Ouvrez [claude.ai](https://claude.ai) dans votre navigateur
2. Ouvrez les outils developpeur (F12)
3. Allez dans **Application > Cookies > claude.ai**
4. Copiez la valeur du cookie \`sessionKey\`

---

## Apercu

\`\`\`
[icone Claude] 90%

Utilisation : 90%
Reinitialisation : 1h 38min
Forfait : Max (5x)
---
MAJ : 14:32
Connecte
---
Parametrage >
  Configurer la session...
  Ouvrir claude.ai
  Desinstaller...
---
Quitter
\`\`\`

---

## Desinstallation

Cliquez sur la jauge > **Parametrage > Desinstaller...**

Ou manuellement :

\`\`\`bash
launchctl bootout "gui/$(id -u)/com.claude.gauge" 2>/dev/null
rm -rf ~/.claude-gauge
rm ~/Library/LaunchAgents/com.claude.gauge.plist
\`\`\`

---

## Details techniques

- Python 3 + rumps (barre de menu macOS)
- PyObjC / AppKit pour l'icone native Claude
- API interne claude.ai (memes endpoints que l'app web)
- Rafraichissement automatique toutes les 2 minutes
- LaunchAgent pour le demarrage au login

## Licence

MIT

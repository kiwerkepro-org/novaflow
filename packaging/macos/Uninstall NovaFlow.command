#!/bin/bash
# NovaFlow Deinstallation (macOS)
#
# Liegt mit im NovaFlow-Setup.dmg neben NovaFlow.app. Es gibt (anders als
# unter Windows mit Inno Setup) keinen eingebauten macOS-Deinstaller fuer ein
# einfaches per Drag&Drop installiertes .app-Bundle, deshalb dieses kleine
# Skript: Doppelklick im Finder startet es ueber Terminal.app.
#
# Entfernt: die App selbst, den Autostart-Eintrag (LaunchAgent), den im
# macOS-Schluesselbund gespeicherten API-Key, und fragt separat nach, ob
# auch die Benutzerdaten (~/.novaflow) geloescht werden sollen.

set -u

APP_PATH="/Applications/NovaFlow.app"
PLIST_PATH="$HOME/Library/LaunchAgents/eu.kiw-schmiede.novaflow.plist"
DATA_DIR="$HOME/.novaflow"

echo "=== NovaFlow Deinstallation ==="
echo ""

# 1. Laufende Instanz beenden, damit weder die App noch ihre Datendatei
#    waehrend des Loeschens gesperrt sind.
pkill -f "NovaFlow.app/Contents/MacOS/NovaFlow" 2>/dev/null

# 2. Autostart (LaunchAgent) entfernen, siehe src/platforms/macos.py
#    (MacAutostart, LAUNCH_AGENT_LABEL "eu.kiw-schmiede.novaflow").
if [ -f "$PLIST_PATH" ]; then
    launchctl unload "$PLIST_PATH" 2>/dev/null
    rm -f "$PLIST_PATH"
    echo "Autostart entfernt."
fi

# 3. Gespeicherten OpenRouter-API-Key aus dem Schluesselbund entfernen.
#    Service-Name "NovaFlow" entspricht SecureConfig.SERVICE_NAME in
#    src/utils/secure_config.py (keyring nutzt darunter denselben Eintrag).
security delete-generic-password -s "NovaFlow" -a "OPENROUTER_API_KEY" >/dev/null 2>&1

# 4. Die App selbst entfernen.
if [ -d "$APP_PATH" ]; then
    rm -rf "$APP_PATH"
    echo "NovaFlow.app entfernt."
else
    echo "Hinweis: NovaFlow.app wurde nicht unter $APP_PATH gefunden."
    echo "Falls sie an einen anderen Ort verschoben wurde, bitte manuell loeschen."
fi

# 5. Benutzerdaten nur nach ausdruecklicher Bestaetigung loeschen, Standard
#    ist "erhalten", damit eine spaetere Neuinstallation Woerterbuch,
#    Ausschnitte, Verlauf, Notizen und Schreibstil wiederfindet.
if [ -d "$DATA_DIR" ]; then
    read -p "Sollen auch die Benutzerdaten (Woerterbuch, Ausschnitte, Verlauf, Notizen, Schreibstil) in $DATA_DIR geloescht werden? [j/N] " ANTWORT
    case "$ANTWORT" in
        [jJ]*)
            rm -rf "$DATA_DIR"
            echo "Benutzerdaten geloescht."
            ;;
        *)
            echo "Benutzerdaten bleiben erhalten."
            ;;
    esac
fi

echo ""
echo "NovaFlow wurde deinstalliert."
read -p "Dieses Fenster kann jetzt geschlossen werden (Enter zum Beenden) " _

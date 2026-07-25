#!/bin/bash
# NovaFlow Deinstallation (macOS)
#
# Liegt mit im NovaFlow-Setup.dmg neben NovaFlow.app. Es gibt (anders als
# unter Windows mit Inno Setup) keinen eingebauten macOS-Deinstaller fuer ein
# einfaches per Drag&Drop installiertes .app-Bundle, deshalb dieses kleine
# Skript: Doppelklick im Finder startet es ueber Terminal.app.
#
# Grundprinzip (siehe installer.iss unter Windows, dieselbe Regel gilt hier):
# alles, was der Nutzer selbst eingegeben oder erzeugt hat, bleibt IMMER
# erhalten. Der API-Schluessel wird nur nach ausdruecklicher Rueckfrage
# entfernt (Standard: behalten). Woerterbuch, Ausschnitte, Verlauf, Notizen
# und Schreibstil in ~/.novaflow werden von diesem Skript NIE angefasst,
# auch nicht mit Nachfrage, das ist allein Sache des Nutzers.

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

# 3. Gespeicherten OpenRouter-API-Key NUR nach ausdruecklicher Bestaetigung
#    aus dem Schluesselbund entfernen. Standard ist "Nein" (behalten), eine
#    spaetere Neuinstallation findet ihn dann automatisch wieder. Service-
#    Name "NovaFlow" entspricht SecureConfig.SERVICE_NAME in
#    src/utils/secure_config.py (keyring nutzt darunter denselben Eintrag).
if security find-generic-password -s "NovaFlow" -a "OPENROUTER_API_KEY" >/dev/null 2>&1; then
    read -p "Soll der gespeicherte OpenRouter-API-Schluessel ebenfalls entfernt werden? [j/N] " ANTWORT
    case "$ANTWORT" in
        [jJ]*)
            security delete-generic-password -s "NovaFlow" -a "OPENROUTER_API_KEY" >/dev/null 2>&1
            echo "API-Schluessel entfernt."
            ;;
        *)
            echo "API-Schluessel bleibt erhalten."
            ;;
    esac
fi

# 4. Die App selbst entfernen.
if [ -d "$APP_PATH" ]; then
    rm -rf "$APP_PATH"
    echo "NovaFlow.app entfernt."
else
    echo "Hinweis: NovaFlow.app wurde nicht unter $APP_PATH gefunden."
    echo "Falls sie an einen anderen Ort verschoben wurde, bitte manuell loeschen."
fi

# 5. Benutzerdaten in ~/.novaflow (Woerterbuch, Ausschnitte, Verlauf,
#    Notizen, Schreibstil) werden von diesem Skript bewusst NIE geloescht
#    und auch nicht danach gefragt. Wer sie loeschen will, macht das
#    manuell selbst.
echo ""
echo "Hinweis: deine persoenlichen NovaFlow-Daten (Woerterbuch, Ausschnitte,"
echo "Verlauf, Notizen, Schreibstil) unter $DATA_DIR bleiben erhalten."
echo "Falls du sie ebenfalls loeschen willst, entferne diesen Ordner manuell."

echo ""
echo "NovaFlow wurde deinstalliert."
read -p "Dieses Fenster kann jetzt geschlossen werden (Enter zum Beenden) " _

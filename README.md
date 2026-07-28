# NovaFlow

NovaFlow ist eine Sprachdiktat Anwendung für Windows und Mac. Per Tastenkombination wird Sprache aufgenommen, in Text umgewandelt, sprachlich veredelt und in das gerade aktive Fenster eingefügt.

## Unterstützung

NovaFlow ist kostenlos und wird in der Freizeit gepflegt. Wer sich bedanken möchte, kann das gerne über PayPal tun:

[Über PayPal spenden](https://www.paypal.com/donate/?hosted_button_id=FLPZ7XCCJNS52)

## Ablauf

Während die Taste gehalten wird:

1. Audio wird aufgenommen. Loslassen der Taste beendet die Aufnahme.
2. Spracherkennung über Voxtral Mini bei OpenRouter (Cloud) oder lokal über Whisper.
3. Nachbearbeitung: Fülllaute entfernen, gesprochene Satzzeichen in echte Zeichen umwandeln, Wörterbuch und Textbausteine anwenden.
4. Veredelung über ein Sprachmodell: Groß- und Kleinschreibung, Zeichensetzung, Stil. Wahlweise über OpenRouter (Cloud), über IONOS AI Model Hub (Cloud, Server in Deutschland, für DSGVO-Konformität) oder lokal über Ollama.
5. Einfügen in das aktive Fenster.

## Installation

Die fertigen Installationsdateien liegen unter [Releases](../../releases).

**Windows:** `NovaFlow-Setup.exe` herunterladen und ausführen, die Installation läuft vollständig geführt ab. Optional kann der Installer auch gleich Ollama für den vollständig lokalen Betrieb ohne Cloud-Zugang mitinstallieren.

**Mac:** `NovaFlow-Setup.dmg` herunterladen, öffnen und NovaFlow.app in den Ordner Programme ziehen. Da die App aktuell nicht signiert/notarisiert ist, zeigt macOS beim allerersten Start die Meldung "kann nicht geöffnet werden, da der Entwickler nicht verifiziert werden kann" (Gatekeeper). Das ist normales macOS-Verhalten für unsignierte Apps, kein Fehler. Abhilfe: im Finder mit Rechtsklick auf NovaFlow.app klicken, dann "Öffnen" wählen und im folgenden Dialog erneut "Öffnen" bestätigen. Alternativ unter Systemeinstellungen → Datenschutz & Sicherheit ganz unten "Trotzdem öffnen" anklicken. Das ist nur beim ersten Start nötig.

Zum Deinstallieren liegt im selben DMG die Datei "Uninstall NovaFlow.command", einfach doppelklicken.

### Zwei Freigaben, die macOS beim ersten Start verlangt

NovaFlow läuft auf dem Mac als Symbol in der Menüleiste, ohne eigenes Fenster im Dock. Damit es überhaupt arbeiten kann, braucht es zwei Berechtigungen:

1. **Mikrofon.** Wird beim ersten Diktat automatisch abgefragt, einfach erlauben.
2. **Bedienungshilfen.** Diese wird NICHT automatisch abgefragt. Ohne sie reagiert die Tastenkombination einfach gar nicht, ohne jede Fehlermeldung. Zu finden unter Systemeinstellungen, Datenschutz und Sicherheit, Bedienungshilfen. Dort NovaFlow in der Liste aktivieren. Falls NovaFlow nicht in der Liste steht, über das Pluszeichen aus dem Ordner Programme hinzufügen. Danach NovaFlow einmal beenden und neu starten.

## Funktionen

- Befehls-Umwandlung: gesprochene Satzzeichen (Punkt, Komma, Fragezeichen und weitere) werden zu echten Zeichen.
- Wörterbuch für feste Korrekturen häufig falsch erkannter Wörter, eigenes Vokabular (Fachbegriffe, Namen) auch aus einer Textdatei importierbar.
- Textbausteine über Triggerwörter.
- Schreibstil-Einstellung (Kategorie und Tonfall).
- Notizbuch für schnelle Notizen.
- Verlauf der letzten Diktate mit Kopieren-Funktion (inklusive Bestätigung), Statistik-Übersicht sowie Volltextsuche mit Datumsfilter.
- Rohtext-Modus: KI-Veredelung bei Bedarf komplett überspringen, umschaltbar per Tray-Symbol oder in den Einstellungen.
- Verschlüsseltes Backup (AES-256-GCM, passwortgeschützt) für Wörterbuch, Textbausteine, Notizbuch, Schreibstil und Verlauf, exportier- und wieder einspielbar.
- Cloud oder vollständig lokal nutzbar (Whisper + Ollama).

## Kostenlos und Premium

Der oben beschriebene Funktionsumfang bleibt dauerhaft kostenlos, für private wie berufliche Nutzung.

Geplant ist eine kostenpflichtige Premium-Version für deutlich aufwendigere Zusatzfunktionen, die über einen serverseitig geprüften Lizenzschlüssel freigeschaltet wird (Zahlungsabwicklung über einen externen Anbieter, unabhängig von einzelnen Nutzerkonten):

- Android-Begleit-App mit Datenabgleich zwischen Desktop und Handy.
- App-bewusste Veredelung: Tonfall passt sich automatisch dem gerade aktiven Zielprogramm an, inklusive Verlaufsfilter nach Zielprogramm.
- Automatische Wörterbuch-Pflege: eine manuelle Korrektur im diktierten Text wird automatisch als Wörterbucheintrag übernommen.
- Sprachbefehle für Korrekturen im laufenden Diktat.
- Mehrere Hotkey-Profile mit jeweils eigenem Schreibstil.
- Später optional ein eigenes Team- beziehungsweise Business-Paket mit zentraler Verwaltung von Wörterbuch und Textbausteinen für mehrere Nutzer.

Diese Premium-Funktionen sind noch nicht verfügbar, siehe die Ideen- und To-Do-Liste des Projekts.

## Voraussetzungen

- Windows 10/11 oder macOS.
- Für den Cloud-Betrieb ein OpenRouter API-Schlüssel (Spracherkennung, optional auch Veredelung).
- Für die DSGVO-konforme Veredelung in Deutschland alternativ ein IONOS AI Model Hub API-Schlüssel (cloud.ionos.com). Betrifft nur die Text-Veredelung, IONOS bietet keine Spracherkennung an.
- Für den lokalen Betrieb Ollama (unter Windows kann das der Installer automatisch mitinstallieren, unter Mac vorher separat von [ollama.com](https://ollama.com) installieren).

## Versionierung

Aktuelle Version siehe [Releases](../../releases).

## Lizenz

Der Quellcode in diesem Repository steht unter der Elastic License 2.0 (siehe [LICENSE](LICENSE)), keine Open-Source-Lizenz im klassischen Sinn. Kurz zusammengefasst: Ansehen, Herunterladen, Verändern sowie private und interne Nutzung sind erlaubt. Nicht erlaubt ist es, NovaFlow oder eine abgeleitete Version als eigenes Produkt oder als gehosteten Dienst weiterzugeben oder weiterzuverkaufen, und Lizenzhinweise sowie eine etwaige Lizenzschlüssel-Prüfung dürfen nicht entfernt oder umgangen werden.

"NovaFlow" sowie ein zugehöriges Logo sind Kennzeichen der KIW-Schmiede, siehe [NOTICE](NOTICE) für Einzelheiten zu Markenschutz und Weitergabebedingungen.

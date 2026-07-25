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
4. Veredelung über ein Sprachmodell: Groß- und Kleinschreibung, Zeichensetzung, Stil. Wahlweise über OpenRouter (Cloud) oder lokal über Ollama.
5. Einfügen in das aktive Fenster.

## Installation

Die fertigen Installationsdateien liegen unter [Releases](../../releases).

**Windows:** `NovaFlow-Setup.exe` herunterladen und ausführen, die Installation läuft vollständig geführt ab. Optional kann der Installer auch gleich Ollama für den vollständig lokalen Betrieb ohne Cloud-Zugang mitinstallieren.

**Mac:** `NovaFlow-Setup.dmg` herunterladen, öffnen und NovaFlow.app in den Ordner Programme ziehen. Da die App aktuell nicht signiert/notarisiert ist, zeigt macOS beim allerersten Start die Meldung "kann nicht geöffnet werden, da der Entwickler nicht verifiziert werden kann" (Gatekeeper). Das ist normales macOS-Verhalten für unsignierte Apps, kein Fehler. Abhilfe: im Finder mit Rechtsklick auf NovaFlow.app klicken, dann "Öffnen" wählen und im folgenden Dialog erneut "Öffnen" bestätigen. Alternativ unter Systemeinstellungen → Datenschutz & Sicherheit ganz unten "Trotzdem öffnen" anklicken. Das ist nur beim ersten Start nötig.

Zum Deinstallieren liegt im selben DMG die Datei "Uninstall NovaFlow.command", einfach doppelklicken.

## Funktionen

- Befehls-Umwandlung: gesprochene Satzzeichen (Punkt, Komma, Fragezeichen und weitere) werden zu echten Zeichen.
- Wörterbuch für feste Korrekturen häufig falsch erkannter Wörter.
- Textbausteine über Triggerwörter.
- Schreibstil-Einstellung (Kategorie und Tonfall).
- Notizbuch für schnelle Notizen.
- Verlauf der letzten Diktate mit Kopieren-Funktion.
- Cloud oder vollständig lokal nutzbar (Whisper + Ollama).

## Voraussetzungen

- Windows 10/11 oder macOS.
- Für den Cloud-Betrieb ein OpenRouter API-Schlüssel.
- Für den lokalen Betrieb Ollama (unter Windows kann das der Installer automatisch mitinstallieren, unter Mac vorher separat von [ollama.com](https://ollama.com) installieren).

## Versionierung

Aktuelle Version siehe [Releases](../../releases).

# NovaFlow

NovaFlow ist eine Sprachdiktat Anwendung für Windows und (in Vorbereitung) Mac. Per Tastenkombination wird Sprache aufgenommen, in Text umgewandelt, sprachlich veredelt und in das gerade aktive Fenster eingefügt.

## Ablauf

Während die Taste gehalten wird:

1. Audio wird aufgenommen. Loslassen der Taste beendet die Aufnahme.
2. Spracherkennung über Voxtral Mini bei OpenRouter (Cloud) oder lokal über Whisper.
3. Nachbearbeitung: Fülllaute entfernen, gesprochene Satzzeichen in echte Zeichen umwandeln, Wörterbuch und Textbausteine anwenden.
4. Veredelung über ein Sprachmodell: Groß- und Kleinschreibung, Zeichensetzung, Stil. Wahlweise über OpenRouter (Cloud) oder lokal über Ollama.
5. Einfügen in das aktive Fenster.

## Installation

Die fertige Setup-Datei liegt unter [Releases](../../releases). Einfach herunterladen und ausführen, die Installation läuft vollständig geführt ab. Optional kann der Installer auch gleich Ollama für den vollständig lokalen Betrieb ohne Cloud-Zugang mitinstallieren.

## Funktionen

- Befehls-Umwandlung: gesprochene Satzzeichen (Punkt, Komma, Fragezeichen und weitere) werden zu echten Zeichen.
- Wörterbuch für feste Korrekturen häufig falsch erkannter Wörter.
- Textbausteine über Triggerwörter.
- Schreibstil-Einstellung (Kategorie und Tonfall).
- Notizbuch für schnelle Notizen.
- Verlauf der letzten Diktate mit Kopieren-Funktion.
- Cloud oder vollständig lokal nutzbar (Whisper + Ollama).

## Voraussetzungen

- Windows 10/11 (Mac-Unterstützung in Vorbereitung).
- Für den Cloud-Betrieb ein OpenRouter API-Schlüssel.
- Für den lokalen Betrieb Ollama (kann vom Installer automatisch mitinstalliert werden).

## Versionierung

Aktuelle Version siehe [Releases](../../releases).

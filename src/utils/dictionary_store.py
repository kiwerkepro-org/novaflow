"""
NovaFlow Dictionary Store
Persistenz für benutzerdefinierte Wörter/Korrektionen (JSON)
"""
import json
import uuid
from pathlib import Path


_DATA_DIR = Path.home() / ".novaflow"
_DICT_FILE = _DATA_DIR / "dictionary.json"


class DictionaryStore:
    """Speichert und verwaltet Wörterbuch-Einträge"""

    def __init__(self):
        """Initialisiere Store — erstelle Directory und Datei falls nötig"""
        _DATA_DIR.mkdir(exist_ok=True, parents=True)
        if not _DICT_FILE.exists():
            _DICT_FILE.write_text('{"entries": []}', encoding="utf-8")

    def get_entries(self) -> list[dict]:
        """Gibt alle Einträge zurück"""
        try:
            data = json.loads(_DICT_FILE.read_text(encoding="utf-8"))
            return data.get("entries", [])
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def add_entry(self, spoken: str, correction: str) -> dict:
        """Füge neuen Eintrag hinzu"""
        entries = self.get_entries()
        entry = {
            "id": str(uuid.uuid4()),
            "spoken": spoken.strip(),
            "correction": correction.strip()
        }
        entries.append(entry)
        self._save(entries)
        return entry

    def delete_entry(self, entry_id: str) -> None:
        """Lösche Eintrag nach ID"""
        entries = [e for e in self.get_entries() if e["id"] != entry_id]
        self._save(entries)

    def update_entry(self, entry_id: str, spoken: str, correction: str) -> None:
        """Update Eintrag"""
        entries = self.get_entries()
        for e in entries:
            if e["id"] == entry_id:
                e["spoken"] = spoken.strip()
                e["correction"] = correction.strip()
                break
        self._save(entries)

    def get_substitutions(self) -> dict[str, str]:
        """Gibt Mapping {spoken_lower: correction} für Substitution"""
        return {
            e["spoken"].lower(): e["correction"]
            for e in self.get_entries()
            if e.get("spoken") and e.get("correction")
        }

    def import_entries(self, pairs: list[tuple[str, str]]) -> dict:
        """Fügt mehrere (spoken, correction)-Paare auf einmal hinzu, z.B. aus
        einer importierten Vokabular-Datei (siehe parse_vocabulary_text()).

        Ueberspringt Paare, deren "spoken"-Wert (ohne Beachtung von
        Gross-/Kleinschreibung) bereits existiert, damit ein zweifacher
        Import derselben Datei keine Duplikate anlegt. Gibt eine kleine
        Zusammenfassung zurueck, die die Oberflaeche direkt anzeigen kann.
        """
        entries = self.get_entries()
        existing_spoken = {e["spoken"].strip().lower() for e in entries if e.get("spoken")}

        added = 0
        skipped = 0
        for spoken, correction in pairs:
            spoken = spoken.strip()
            correction = correction.strip()
            if not spoken or not correction:
                continue
            key = spoken.lower()
            if key in existing_spoken:
                skipped += 1
                continue
            entries.append({"id": str(uuid.uuid4()), "spoken": spoken, "correction": correction})
            existing_spoken.add(key)
            added += 1

        if added:
            self._save(entries)

        return {"added": added, "skipped": skipped}

    def _save(self, entries: list) -> None:
        """Speichere Einträge als JSON"""
        _DICT_FILE.write_text(
            json.dumps({"entries": entries}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )


def parse_vocabulary_text(text: str) -> list[tuple[str, str]]:
    """Liest eine importierte Vokabular-/Wörterbuch-Datei zeilenweise ein.

    Unterstuetzt zwei Zeilenformen, gemischt in derselben Datei:

    - Ein einzelnes Wort/Fachbegriff pro Zeile, z.B. "TensorFlow" -> wird als
      (spoken, correction) mit identischem Wert auf beiden Seiten
      uebernommen. Das erzwingt beim Post-Processing (siehe
      TextProcessor.apply_dictionary) die exakte Schreibweise, sobald das
      Wort in beliebiger Gross-/Kleinschreibung erkannt wird, genau das ist
      der Sinn eines "eigenen Vokabulars" fuer Eigennamen/Fachbegriffe, die
      Whisper sonst regelmaessig anders schreibt.
    - Ein Korrektur-Paar "falsch erkannt=richtig" pro Zeile, wie es die
      Wörterbuch-Seite in gui_settings_modal.py auch von Hand anlegt.
      Getrennt durch "=", ein Tabulator, "->" oder "," (in dieser
      Reihenfolge geprueft, ein Trennzeichen pro Zeile reicht).

    Leerzeilen und Zeilen, die mit "#" beginnen (Kommentare), werden
    uebersprungen. Bewusst FEHLERTOLERANT statt streng: eine einzelne
    kaputte Zeile in einer grossen importierten Liste soll nicht den
    kompletten Import verhindern, sie wird einfach ignoriert.
    """
    pairs: list[tuple[str, str]] = []
    separators = ("=", "\t", "->", ",")

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        spoken, correction = None, None
        for sep in separators:
            if sep in line:
                left, _, right = line.partition(sep)
                left, right = left.strip(), right.strip()
                if left and right:
                    spoken, correction = left, right
                break

        if spoken is None:
            # Kein Trennzeichen gefunden bzw. eine Seite war leer:
            # die ganze Zeile als Vokabular-Wort behandeln (siehe Docstring).
            spoken = correction = line

        pairs.append((spoken, correction))

    return pairs


# Singleton
dictionary_store = DictionaryStore()

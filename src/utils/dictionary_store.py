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

    def _save(self, entries: list) -> None:
        """Speichere Einträge als JSON"""
        _DICT_FILE.write_text(
            json.dumps({"entries": entries}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )


# Singleton
dictionary_store = DictionaryStore()

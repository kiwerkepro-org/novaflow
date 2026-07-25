"""
NovaFlow Notes Store
Persistenz für Notizbuch-Einträge (Notizen mit Timestamp)
"""
import json
import uuid
from pathlib import Path
from datetime import datetime


_DATA_DIR = Path.home() / ".novaflow"
_NOTES_FILE = _DATA_DIR / "notes.json"


class NotesStore:
    """Speichert und verwaltet Notiz-Einträge"""

    def __init__(self):
        """Initialisiere Store — erstelle Directory und Datei falls nötig"""
        _DATA_DIR.mkdir(exist_ok=True, parents=True)
        if not _NOTES_FILE.exists():
            _NOTES_FILE.write_text('{"entries": []}', encoding="utf-8")

    def get_entries(self) -> list[dict]:
        """Gibt alle Einträge zurück, neueste zuerst"""
        try:
            data = json.loads(_NOTES_FILE.read_text(encoding="utf-8"))
            entries = data.get("entries", [])
            return sorted(entries, key=lambda e: e.get("created_at", ""), reverse=True)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def add_entry(self, text: str) -> dict:
        """Füge neue Notiz hinzu"""
        entries = self.get_entries()
        entry = {
            "id": str(uuid.uuid4()),
            "text": text.strip(),
            "created_at": datetime.now().isoformat()
        }
        entries.append(entry)
        self._save(entries)
        return entry

    def delete_entry(self, entry_id: str) -> None:
        """Lösche Eintrag nach ID"""
        entries = [e for e in self.get_entries() if e["id"] != entry_id]
        self._save(entries)

    def _save(self, entries: list) -> None:
        """Speichere Einträge als JSON"""
        _NOTES_FILE.write_text(
            json.dumps({"entries": entries}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )


# Singleton
notes_store = NotesStore()

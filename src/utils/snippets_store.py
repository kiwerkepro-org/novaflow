"""
NovaFlow Snippets Store
Persistenz für Kurztext-Erweiterungen (Ausschnitte)
"""
import json
import uuid
from pathlib import Path


_DATA_DIR = Path.home() / ".novaflow"
_SNIPPETS_FILE = _DATA_DIR / "snippets.json"


class SnippetsStore:
    """Speichert und verwaltet Snippet-Einträge (Trigger → Expansion)"""

    def __init__(self):
        """Initialisiere Store — erstelle Directory und Datei falls nötig"""
        _DATA_DIR.mkdir(exist_ok=True, parents=True)
        if not _SNIPPETS_FILE.exists():
            _SNIPPETS_FILE.write_text('{"entries": []}', encoding="utf-8")

    def get_entries(self) -> list[dict]:
        """Gibt alle Einträge zurück"""
        try:
            data = json.loads(_SNIPPETS_FILE.read_text(encoding="utf-8"))
            return data.get("entries", [])
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def add_entry(self, trigger: str, expansion: str) -> dict:
        """Füge neuen Snippet hinzu"""
        entries = self.get_entries()
        entry = {
            "id": str(uuid.uuid4()),
            "trigger": trigger.strip(),
            "expansion": expansion.strip()
        }
        entries.append(entry)
        self._save(entries)
        return entry

    def delete_entry(self, entry_id: str) -> None:
        """Lösche Eintrag nach ID"""
        entries = [e for e in self.get_entries() if e["id"] != entry_id]
        self._save(entries)

    def update_entry(self, entry_id: str, trigger: str, expansion: str) -> None:
        """Update Eintrag"""
        entries = self.get_entries()
        for e in entries:
            if e["id"] == entry_id:
                e["trigger"] = trigger.strip()
                e["expansion"] = expansion.strip()
                break
        self._save(entries)

    def get_expansions(self) -> dict[str, str]:
        """Gibt Mapping {trigger_lower: expansion} für Expansion"""
        return {
            e["trigger"].lower(): e["expansion"]
            for e in self.get_entries()
            if e.get("trigger") and e.get("expansion")
        }

    def _save(self, entries: list) -> None:
        """Speichere Einträge als JSON"""
        _SNIPPETS_FILE.write_text(
            json.dumps({"entries": entries}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )


# Singleton
snippets_store = SnippetsStore()

"""
NovaFlow History Store – Speichert vergangene Transkriptionen im Arbeitsspeicher
(optional: JSON-Persistenz in ~/.novaflow/history.json)
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict


MAX_ENTRIES = 50
HISTORY_FILE = Path.home() / ".novaflow" / "history.json"


class HistoryStore:
    """In-Memory + JSON-Persistenz für Transkriptions-Verlauf"""

    def __init__(self):
        self._entries: List[Dict] = []
        self._load()

    def _load(self):
        """Lade bestehenden Verlauf aus JSON"""
        try:
            HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            if HISTORY_FILE.exists():
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    self._entries = json.load(f)
        except Exception:
            self._entries = []

    def _save(self):
        """Speichere Verlauf in JSON"""
        try:
            HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self._entries[-MAX_ENTRIES:], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def add(self, raw_text: str, refined_text: str) -> Dict:
        """Fügt eine neue Transkription hinzu"""
        entry = {
            "id": str(uuid.uuid4()),
            "raw": raw_text,
            "text": refined_text,
            "created_at": datetime.now().isoformat(),
        }
        self._entries.append(entry)
        if len(self._entries) > MAX_ENTRIES:
            self._entries = self._entries[-MAX_ENTRIES:]
        self._save()
        return entry

    def get_all(self) -> List[Dict]:
        """Gibt alle Einträge zurück (neueste zuerst) – liest Datei neu ein"""
        self._load()
        return list(reversed(self._entries))

    def clear(self):
        """Löscht den gesamten Verlauf"""
        self._entries = []
        self._save()

    def __len__(self):
        return len(self._entries)


# Singleton
history_store = HistoryStore()

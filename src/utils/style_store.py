"""
NovaFlow Style Store
Persistenz für Schreibstil-Konfiguration (Kategorie + Ton)
"""
import json
from pathlib import Path


_DATA_DIR = Path.home() / ".novaflow"
_STYLE_FILE = _DATA_DIR / "style.json"

CATEGORIES = ["personal", "work", "email", "other"]
TONES = ["formal", "casual", "excited"]
DEFAULT_CATEGORY = "work"
DEFAULT_TONE = "formal"


class StyleStore:
    """Speichert aktive Kategorie und Ton für den Schreibstil"""

    def __init__(self):
        """Initialisiere Store — erstelle Directory und Datei falls nötig"""
        _DATA_DIR.mkdir(exist_ok=True, parents=True)
        if not _STYLE_FILE.exists():
            self._save(DEFAULT_CATEGORY, DEFAULT_TONE)

    def get_style(self) -> dict:
        """Gibt {'category': str, 'tone': str} zurück"""
        try:
            data = json.loads(_STYLE_FILE.read_text(encoding="utf-8"))
            category = data.get("category", DEFAULT_CATEGORY)
            tone = data.get("tone", DEFAULT_TONE)
            if category not in CATEGORIES:
                category = DEFAULT_CATEGORY
            if tone not in TONES:
                tone = DEFAULT_TONE
            return {"category": category, "tone": tone}
        except (json.JSONDecodeError, FileNotFoundError):
            return {"category": DEFAULT_CATEGORY, "tone": DEFAULT_TONE}

    def set_style(self, category: str = None, tone: str = None) -> None:
        """Aktualisiert Kategorie und/oder Ton"""
        current = self.get_style()
        new_cat = category if category in CATEGORIES else current["category"]
        new_tone = tone if tone in TONES else current["tone"]
        self._save(new_cat, new_tone)

    def _save(self, category: str, tone: str) -> None:
        """Speichere Stil als JSON"""
        _STYLE_FILE.write_text(
            json.dumps({"category": category, "tone": tone}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )


# Singleton
style_store = StyleStore()

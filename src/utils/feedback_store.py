"""
NovaFlow Feedback Store
Persistenz für Transkriptions-Korrektionen (Lernschleife für Few-Shot Prompting)
"""
import json
import uuid
from pathlib import Path
from datetime import datetime


_DATA_DIR = Path.home() / ".novaflow"
_FEEDBACK_FILE = _DATA_DIR / "feedback.json"


class FeedbackStore:
    """Speichert und verwaltet Feedback-Einträge für adaptive Few-Shot Learning"""

    def __init__(self):
        """Initialisiere Store — erstelle Directory und Datei falls nötig"""
        _DATA_DIR.mkdir(exist_ok=True, parents=True)
        if not _FEEDBACK_FILE.exists():
            _FEEDBACK_FILE.write_text('{"entries": []}', encoding="utf-8")

    def get_entries(self) -> list[dict]:
        """Gibt alle Feedback-Einträge zurück"""
        try:
            data = json.loads(_FEEDBACK_FILE.read_text(encoding="utf-8"))
            return data.get("entries", [])
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def add_feedback(
        self,
        whisper_raw: str,
        llm_output: str,
        user_correction: str = None,
        rating: str = "neutral"
    ) -> dict:
        """
        Füge Feedback-Eintrag hinzu

        Args:
            whisper_raw: Original Whisper-Transkription
            llm_output: LLM-Korrektur (vor User-Feedback)
            user_correction: Optional: Was der User stattdessen sagte
            rating: "good" | "bad" | "corrected" | "neutral"
        """
        entries = self.get_entries()
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "whisper_raw": whisper_raw.strip(),
            "llm_output": llm_output.strip(),
            "user_correction": user_correction.strip() if user_correction else None,
            "rating": rating
        }
        entries.append(entry)
        self._save(entries)
        return entry

    def delete_entry(self, entry_id: str) -> None:
        """Lösche Eintrag nach ID"""
        entries = [e for e in self.get_entries() if e["id"] != entry_id]
        self._save(entries)

    def get_best_examples(self, n: int = 3) -> list[dict]:
        """
        Gibt die besten Lernbeispiele zurück (neueste + mit Korrektur)

        Args:
            n: Anzahl Beispiele

        Returns:
            Liste von Einträgen mit user_correction (sortiert: neueste zuerst)
        """
        entries = self.get_entries()
        corrected = [e for e in entries if e.get("user_correction")]
        corrected.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return corrected[:n]

    def get_correction_count(self) -> int:
        """Gibt Anzahl Korrektionen zurück (für Threshold-Check: ≥5 for few-shot)"""
        return len([e for e in self.get_entries() if e.get("user_correction")])

    def export_jsonl(self, output_path: str = None) -> str:
        """
        Exportiert Feedback als HuggingFace Chat-Format JSONL
        (für Fine-Tuning)

        Args:
            output_path: Ziel-Pfad (default: ~/.novaflow/feedback_export.jsonl)

        Returns:
            Pfad der exportierten Datei
        """
        if not output_path:
            output_path = str(_DATA_DIR / "feedback_export.jsonl")

        entries = self.get_entries()

        with open(output_path, "w", encoding="utf-8") as f:
            for entry in entries:
                if not entry.get("user_correction"):
                    continue

                record = {
                    "messages": [
                        {
                            "role": "system",
                            "content": "Du bist ein hochpräziser Korrektor-Agent für Audiotranskripte."
                        },
                        {
                            "role": "user",
                            "content": entry.get("whisper_raw", "")
                        },
                        {
                            "role": "assistant",
                            "content": entry.get("user_correction", "")
                        }
                    ]
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return output_path

    def _save(self, entries: list) -> None:
        """Speichere Einträge als JSON"""
        _FEEDBACK_FILE.write_text(
            json.dumps({"entries": entries}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )


# Singleton
feedback_store = FeedbackStore()

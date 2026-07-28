"""
NovaFlow History Store – Speichert vergangene Transkriptionen im Arbeitsspeicher
(optional: JSON-Persistenz in ~/.novaflow/history.json)
"""
import json
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional


MAX_ENTRIES = 50
HISTORY_FILE = Path.home() / ".novaflow" / "history.json"

# Erkennung sensibler Daten im Verlauf (JJ, 2026-07-28): eine lange
# Ziffernfolge (z.B. versehentlich diktierte Kreditkarten- oder
# Kontonummer) soll im gespeicherten Verlauf nicht im Klartext stehenbleiben.
# Mindestens 6 zusammenhaengende Ziffern, dabei duerfen einzelne Leerzeichen,
# Punkte oder Bindestriche als Trenner vorkommen (typisch, wenn eine Nummer
# in Gruppen diktiert wird, z.B. "1234 5678 9012 3456"). Bewusst nur
# Mustererkennung, keine Garantie: kuerzere Zahlen (z.B. Postleitzahlen)
# bleiben unangetastet, laengere unkritische Zahlen (z.B. Telefonnummern)
# werden im Zweifel trotzdem maskiert, das ist als Sicherheitsnetz gewollt.
_SENSITIVE_DIGIT_RUN = re.compile(r'\d(?:[ .\-]?\d){5,}')


def mask_sensitive_numbers(text: str) -> str:
    """Maskiert lange Ziffernfolgen in einem Text, die letzten zwei Ziffern
    bleiben zur Wiedererkennung sichtbar, Trennzeichen bleiben erhalten
    (z.B. "1234 5678 9012 3456" -> "•••• •••• •••• ••56").

    Reine Textfunktion ohne Abhaengigkeiten, damit sie sich isoliert testen
    laesst (siehe tests/). Wird ausschliesslich beim Speichern in den
    Verlauf angewendet (siehe HistoryStore.add), NICHT auf den Text, der
    tatsaechlich ins Zielfenster eingefuegt wird – das eigentliche Diktat
    des Nutzers darf dadurch nicht veraendert werden.
    """
    if not text:
        return text

    def _mask(match: "re.Match") -> str:
        run = match.group(0)
        total_digits = sum(1 for ch in run if ch.isdigit())
        keep_from = max(total_digits - 2, 0)
        seen = 0
        out = []
        for ch in run:
            if ch.isdigit():
                seen += 1
                out.append(ch if seen > keep_from else "•")
            else:
                out.append(ch)
        return "".join(out)

    return _SENSITIVE_DIGIT_RUN.sub(_mask, text)


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
        """Fügt eine neue Transkription hinzu.

        Speichert bewusst die maskierte Fassung (siehe mask_sensitive_numbers
        oben): der Verlauf ist eine dauerhafte Ablage auf der Festplatte, das
        eigentliche Diktat (was tatsaechlich ins Zielfenster eingefuegt wird)
        bleibt davon unberuehrt, siehe NovaFlowApp.process_audio in main.py.
        """
        entry = {
            "id": str(uuid.uuid4()),
            "raw": mask_sensitive_numbers(raw_text),
            "text": mask_sensitive_numbers(refined_text),
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


def compute_history_stats(entries: List[Dict], now: Optional[datetime] = None) -> Dict:
    """Wertet die vorhandenen Verlaufseintraege aus (JJ, 2026-07-27).

    Reine Funktion ohne Qt-Abhaengigkeit, damit sie sich isoliert testen
    laesst: die Rohdaten (raw/text/created_at pro Eintrag) liegen dank
    HistoryStore.add() bereits vollstaendig vor, hier passiert nur noch die
    Auswertung. Rechnet bewusst NUR mit den Eintraegen, die aktuell im
    Verlauf stehen (siehe MAX_ENTRIES oben, die aeltesten fallen irgendwann
    heraus), das ist derselbe Datenstand, den die Verlauf-Seite ohnehin
    zeigt.

    "now" ist optional injizierbar, damit Tests nicht vom tatsaechlichen
    Aufrufzeitpunkt abhaengen.
    """
    if now is None:
        now = datetime.now()

    if not entries:
        return {
            "count": 0,
            "total_words": 0,
            "avg_words": 0.0,
            "longest_words": 0,
            "shortest_words": 0,
            "first_date": None,
            "last_date": None,
            "today_count": 0,
            "last_7_days_count": 0,
            "avg_refinement_word_delta": 0.0,
        }

    word_counts = []
    raw_word_counts = []
    dates = []
    today_count = 0
    last_7_days_count = 0
    week_cutoff = now - timedelta(days=7)

    for entry in entries:
        text = entry.get("text") or ""
        raw = entry.get("raw") or ""
        word_counts.append(len(text.split()))
        raw_word_counts.append(len(raw.split()))

        created_at = entry.get("created_at")
        if created_at:
            try:
                dt = datetime.fromisoformat(created_at)
            except ValueError:
                dt = None
            if dt:
                dates.append(dt)
                if dt.date() == now.date():
                    today_count += 1
                if dt >= week_cutoff:
                    last_7_days_count += 1

    count = len(entries)
    total_words = sum(word_counts)
    deltas = [w - r for w, r in zip(word_counts, raw_word_counts)]

    return {
        "count": count,
        "total_words": total_words,
        "avg_words": total_words / count,
        "longest_words": max(word_counts),
        "shortest_words": min(word_counts),
        "first_date": min(dates).isoformat() if dates else None,
        "last_date": max(dates).isoformat() if dates else None,
        "today_count": today_count,
        "last_7_days_count": last_7_days_count,
        "avg_refinement_word_delta": sum(deltas) / len(deltas) if deltas else 0.0,
    }


DATE_FILTERS = ("all", "today", "7d", "30d")


def filter_history_entries(
    entries: List[Dict],
    query: str = "",
    date_filter: str = "all",
    now: Optional[datetime] = None,
) -> List[Dict]:
    """Volltextsuche + Datumsfilter ueber vorhandene Verlaufseintraege
    (JJ, 2026-07-27). Wie compute_history_stats() eine reine Funktion ohne
    Qt-Abhaengigkeit, die GUI liefert nur Suchtext/Filterwahl an und zeigt
    das Ergebnis an.

    query: Substring-Suche (Gross-/Kleinschreibung egal) ueber sowohl den
    veredelten Text als auch den Rohtext, damit ein Diktat auch dann
    gefunden wird, wenn der gesuchte Begriff nur in der unveredelten
    Version auftaucht (z.B. weil die KI-Veredelung ihn umformuliert hat).

    date_filter: "all", "today", "7d" oder "30d" (siehe DATE_FILTERS).
    Eintraege mit fehlendem/kaputtem Zeitstempel werden bei aktivem
    Datumsfilter ausgeschlossen, da ihr Alter nicht verifizierbar ist,
    bleiben bei "all" aber weiterhin sichtbar.
    """
    if now is None:
        now = datetime.now()

    query = (query or "").strip().lower()
    if date_filter not in DATE_FILTERS:
        date_filter = "all"

    window = {"7d": timedelta(days=7), "30d": timedelta(days=30)}.get(date_filter)

    result = []
    for entry in entries:
        if query:
            haystack = f"{entry.get('text') or ''} {entry.get('raw') or ''}".lower()
            if query not in haystack:
                continue

        if date_filter != "all":
            created_at = entry.get("created_at")
            dt = None
            if created_at:
                try:
                    dt = datetime.fromisoformat(created_at)
                except ValueError:
                    dt = None
            if dt is None:
                continue
            if date_filter == "today":
                if dt.date() != now.date():
                    continue
            elif window is not None and dt < now - window:
                continue

        result.append(entry)

    return result


# Singleton
history_store = HistoryStore()

"""Tests fuer die Verlauf-Statistik (JJ, 2026-07-27)."""
import ast
import os
import sys
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT + "/src")

from utils.history_store import compute_history_stats

ok = []
fail = []


def check(n, c):
    (ok if c else fail).append(n)
    print(("  OK   " if c else "  FEHL ") + n)


def entry(raw, text, dt):
    return {"raw": raw, "text": text, "created_at": dt.isoformat()}


print("\n=== compute_history_stats: leerer Verlauf ===")
s = compute_history_stats([])
check("count 0", s["count"] == 0)
check("keine Division durch 0 (avg_words 0.0)", s["avg_words"] == 0.0)
check("first_date/last_date None", s["first_date"] is None and s["last_date"] is None)

print("\n=== compute_history_stats: normaler Verlauf ===")
now = datetime(2026, 7, 27, 12, 0, 0)
entries = [
    entry("hallo welt", "Hallo Welt.", now - timedelta(days=10)),           # 2 Woerter, ausserhalb 7-Tage-Fenster
    entry("dies ist ein test heute", "Dies ist ein Test heute.", now),       # 5 Woerter, heute
    entry("kurzer text gestern hier", "Kurzer Text gestern.", now - timedelta(days=1)),  # 3 Woerter, in 7 Tagen
]
s = compute_history_stats(entries, now=now)
check("count stimmt", s["count"] == 3)
check("total_words stimmt (2+5+3)", s["total_words"] == 10)
check("avg_words stimmt", abs(s["avg_words"] - 10 / 3) < 1e-9)
check("longest_words stimmt", s["longest_words"] == 5)
check("shortest_words stimmt", s["shortest_words"] == 2)
check("today_count zaehlt nur den heutigen Eintrag", s["today_count"] == 1)
check("last_7_days_count zaehlt heute+gestern, nicht vor 10 Tagen", s["last_7_days_count"] == 2)
check("first_date ist der aelteste Eintrag", s["first_date"] == (now - timedelta(days=10)).isoformat())
check("last_date ist der neueste Eintrag", s["last_date"] == now.isoformat())

print("\n=== compute_history_stats: Veredelungs-Delta ===")
entries2 = [
    entry("kurzer rohtext", "Ein deutlich laengerer veredelter Text mit mehr Woertern.", now),
]
s2 = compute_history_stats(entries2, now=now)
raw_words = len("kurzer rohtext".split())
text_words = len("Ein deutlich laengerer veredelter Text mit mehr Woertern.".split())
check("avg_refinement_word_delta positiv wenn Veredelung Text verlaengert",
      s2["avg_refinement_word_delta"] == text_words - raw_words)

print("\n=== compute_history_stats: robust gegen kaputte Zeitstempel ===")
entries3 = [{"raw": "x", "text": "ein wort mehr", "created_at": "nicht-parsebar"}]
s3 = compute_history_stats(entries3, now=now)
check("kein Absturz bei kaputtem Datum", s3["count"] == 1)
check("Datum bleibt None statt Fehler", s3["first_date"] is None)

# --- _format_history_stats aus gui_settings_modal.py per AST extrahieren,
# genau wie tests/test_modal.py und tests/test_history_copy_feedback.py es
# fuer andere Methoden schon tun, damit PyQt6 hierfuer nicht installiert
# sein muss. ---
SRC = ROOT + "/src/gui_settings_modal.py"
src = open(SRC, encoding="utf-8").read()
tree = ast.parse(src)
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_format_history_stats")
mod = ast.Module(body=[method], type_ignores=[])
ns = {}
exec(compile(mod, SRC, "exec"), ns)


class S:
    pass


print("\n=== _format_history_stats ===")
s4 = S()
text_empty = ns["_format_history_stats"](s4, compute_history_stats([]))
check("leerer Verlauf -> Hinweistext, kein Crash", "Noch keine" in text_empty)

s5 = S()
text_full = ns["_format_history_stats"](s5, s)
check("Anzahl Diktate im Text", "3 Diktate" in text_full)
check("Deutsches Dezimaltrennzeichen (Komma statt Punkt)", "3,3" in text_full)
check("Heute-Zahl im Text", "Heute: 1" in text_full)
check("7-Tage-Zahl im Text", "Letzte 7 Tage: 2" in text_full)

s6 = S()
text_delta = ns["_format_history_stats"](s6, s2)
check("Veredelungs-Hinweis erscheint bei spuerbarer Differenz", "KI-Veredelung" in text_delta)
check("Richtung 'mehr' korrekt benannt", "mehr" in text_delta)

print("\n=== ERGEBNIS ===")
print(f"bestanden: {len(ok)}   fehlgeschlagen: {len(fail)}")
if fail:
    print("FEHLER:", fail)
    sys.exit(1)

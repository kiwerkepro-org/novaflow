"""Tests fuer die Volltextsuche mit Datumsfilter im Verlauf (JJ, 2026-07-27)."""
import os
import sys
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT + "/src")

from utils.history_store import filter_history_entries, DATE_FILTERS

ok = []
fail = []


def check(n, c):
    (ok if c else fail).append(n)
    print(("  OK   " if c else "  FEHL ") + n)


def entry(raw, text, dt):
    return {"raw": raw, "text": text, "created_at": dt.isoformat()}


now = datetime(2026, 7, 27, 12, 0, 0)
entries = [
    entry("nowa flow starten", "NovaFlow starten.", now),                          # heute
    entry("kaffee bestellen bitte", "Kaffee bestellen, bitte.", now - timedelta(days=2)),  # letzte 7 Tage
    entry("altes projekt notiz", "Altes Projekt, Notiz.", now - timedelta(days=20)),       # letzte 30 Tage
    entry("uralter eintrag hier", "Uralter Eintrag hier.", now - timedelta(days=90)),      # ausserhalb 30 Tage
]

print("\n=== filter_history_entries: DATE_FILTERS Reihenfolge ===")
check(
    "Reihenfolge stimmt mit der Combobox in gui_settings_modal.py ueberein "
    "(Alle, Heute, Letzte 7 Tage, Letzte 30 Tage)",
    DATE_FILTERS == ("all", "today", "7d", "30d"),
)

print("\n=== filter_history_entries: ohne Suchtext ===")
check("'all' liefert alle 4 Eintraege", len(filter_history_entries(entries, "", "all", now=now)) == 4)
check("'today' liefert nur den heutigen Eintrag", len(filter_history_entries(entries, "", "today", now=now)) == 1)
check("'7d' liefert heute+vorgestern", len(filter_history_entries(entries, "", "7d", now=now)) == 2)
check("'30d' schliesst den 90-Tage-Eintrag aus", len(filter_history_entries(entries, "", "30d", now=now)) == 3)

print("\n=== filter_history_entries: Volltextsuche ===")
hits = filter_history_entries(entries, "kaffee", "all", now=now)
check("Suche im veredelten Text findet Treffer", len(hits) == 1 and hits[0]["text"].startswith("Kaffee"))

hits2 = filter_history_entries(entries, "nowa flow", "all", now=now)
check(
    "Suche findet Treffer auch nur im Rohtext (Begriff steht nicht mehr im veredelten Text)",
    len(hits2) == 1 and hits2[0]["raw"] == "nowa flow starten",
)

hits3 = filter_history_entries(entries, "KAFFEE", "all", now=now)
check("Suche ist gross/kleinschreibungs-unabhaengig", len(hits3) == 1)

hits4 = filter_history_entries(entries, "xyz-nicht-vorhanden", "all", now=now)
check("kein Treffer -> leere Liste, kein Fehler", hits4 == [])

print("\n=== filter_history_entries: Suche + Datumsfilter kombiniert ===")
combo = filter_history_entries(entries, "eintrag", "30d", now=now)
check("Uralter Eintrag passt textlich, faellt aber durch den Datumsfilter", combo == [])

combo2 = filter_history_entries(entries, "projekt", "30d", now=now)
check("Altes Projekt passt zu Text UND Datumsfilter", len(combo2) == 1)

print("\n=== filter_history_entries: robust gegen kaputte/fehlende Zeitstempel ===")
broken = [{"raw": "x", "text": "ein test", "created_at": None}]
check(
    "ohne Datumsfilter bleibt der Eintrag trotzdem sichtbar",
    len(filter_history_entries(broken, "", "all", now=now)) == 1,
)
check(
    "mit aktivem Datumsfilter wird er ausgeschlossen (Alter nicht verifizierbar)",
    len(filter_history_entries(broken, "", "today", now=now)) == 0,
)

print("\n=== filter_history_entries: unbekannter Filterwert faellt auf 'all' zurueck ===")
check(
    "unbekannter date_filter-Wert -> wie 'all' behandelt, kein Crash",
    len(filter_history_entries(entries, "", "irgendwas-falsches", now=now)) == 4,
)

print("\n=== ERGEBNIS ===")
print(f"bestanden: {len(ok)}   fehlgeschlagen: {len(fail)}")
if fail:
    print("FEHLER:", fail)
    sys.exit(1)

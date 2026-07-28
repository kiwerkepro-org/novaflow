"""Tests fuer die Erkennung/Maskierung sensibler Daten im Verlauf
(JJ, 2026-07-28, Version 1.0.4). Reine Textlogik, siehe
utils/history_store.py mask_sensitive_numbers()."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT + "/src")

from utils.history_store import mask_sensitive_numbers, HistoryStore

ok = []
fail = []


def check(n, c):
    (ok if c else fail).append(n)
    print(("  OK   " if c else "  FEHL ") + n)


print("\n=== mask_sensitive_numbers: lange Ziffernfolgen werden maskiert ===")
kartennummer = "Meine Kartennummer ist 1234 5678 9012 3456, bitte notieren."
masked = mask_sensitive_numbers(kartennummer)
check("Ziffern sind maskiert", "1234 5678 9012 3456" not in masked)
check("letzte zwei Ziffern bleiben sichtbar", masked.endswith("56, bitte notieren.") or "56" in masked)
check("Maskierungszeichen vorhanden", "•" in masked)
check("Umgebender Text bleibt erhalten", "Meine Kartennummer ist" in masked and "bitte notieren." in masked)

print("\n=== mask_sensitive_numbers: kurze Zahlen bleiben unangetastet ===")
plz = "Die Postleitzahl ist 12345."
check("5-stellige Zahl (z.B. PLZ) bleibt sichtbar", mask_sensitive_numbers(plz) == plz)

print("\n=== mask_sensitive_numbers: Rand- und Leerfaelle ===")
check("leerer Text bleibt leer", mask_sensitive_numbers("") == "")
check("Text ohne Zahlen bleibt unveraendert", mask_sensitive_numbers("Hallo Welt, wie geht es dir?") == "Hallo Welt, wie geht es dir?")
check("None bricht nicht ab", mask_sensitive_numbers(None) is None)

print("\n=== HistoryStore.add(): maskiert automatisch vor dem Speichern ===")
store = HistoryStore()
store._entries = []  # isoliert von echten, evtl. vorhandenen Eintraegen
entry = store.add("meine iban ist 1234 5678 9012 3456 7890", "Meine IBAN ist 1234 5678 9012 3456 7890.")
check("Rohtext im Verlauf ist maskiert", "1234 5678 9012 3456 7890" not in entry["raw"])
check("veredelter Text im Verlauf ist maskiert", "1234 5678 9012 3456 7890" not in entry["text"])

print("\n=== ERGEBNIS ===")
print(f"bestanden: {len(ok)}   fehlgeschlagen: {len(fail)}")
if fail:
    print("FEHLER:", fail)
    sys.exit(1)

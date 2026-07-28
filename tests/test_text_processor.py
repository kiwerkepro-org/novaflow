"""Tests fuer text_processor.py: Absatzbildung nach 5-6 Saetzen (JJ, 2026-07-28,
Version 1.0.4). Reine Textlogik, keine Betriebssystem-Abhaengigkeit."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT + "/src")

from text_processor import TextProcessor

ok = []
fail = []


def check(n, c):
    (ok if c else fail).append(n)
    print(("  OK   " if c else "  FEHL ") + n)


tp = TextProcessor(language="de")

print("\n=== insert_paragraph_breaks: kurzer Text bleibt unveraendert ===")
short_text = "Kurzer Satz. Noch einer. Und ein dritter."
check("kein Absatz bei weniger als 6 Saetzen", "\n\n" not in tp.insert_paragraph_breaks(short_text))
check("Text bleibt inhaltlich gleich", tp.insert_paragraph_breaks(short_text) == short_text)

print("\n=== insert_paragraph_breaks: laengerer Text bekommt Absaetze ===")
sentences = [f"Das ist Satz Nummer {i}." for i in range(1, 13)]
long_text = " ".join(sentences)
result = tp.insert_paragraph_breaks(long_text)
check("mindestens ein Absatz eingefuegt", "\n\n" in result)
check("kein Satz verloren gegangen", all(s in result for s in sentences))

# 12 Saetze -> abwechselnd 5, dann 6, dann Rest: Bloecke [1-5], [6-11], [12]
blocks = result.split("\n\n")
check("Text in drei Bloecke aufgeteilt (5 + 6 + 1 Saetze)", len(blocks) == 3)
check("kein Block ist leer", all(b.strip() for b in blocks))
check("erster Block enthaelt genau Satz 1 bis 5", blocks[0] == " ".join(sentences[0:5]))
check("zweiter Block enthaelt genau Satz 6 bis 11", blocks[1] == " ".join(sentences[5:11]))
check("dritter Block enthaelt genau Satz 12", blocks[2] == sentences[11])

print("\n=== insert_paragraph_breaks: greift nicht ein, wenn bereits Zeilenumbruch vorhanden ===")
with_break = "Erster Satz. Zweiter Satz.\nDritter Satz. Vierter Satz. Fuenfter Satz. Sechster Satz."
check(
    "Text mit vorhandenem Zeilenumbruch bleibt unangetastet",
    tp.insert_paragraph_breaks(with_break) == with_break,
)

print("\n=== insert_paragraph_breaks: leerer Text ===")
check("leerer String bleibt leer", tp.insert_paragraph_breaks("") == "")
check("None-artiger Input bricht nicht ab", tp.insert_paragraph_breaks(None) is None)

print("\n=== process(): komplette Pipeline bricht durch neue Methode nicht ===")
raw = "das ist ein test. das system funktioniert gut. äh das war gut."
processed = tp.process(raw)
check("process() laeuft weiterhin durch (kein Fehler, kein leeres Ergebnis)", bool(processed))

print("\n=== ERGEBNIS ===")
print(f"bestanden: {len(ok)}   fehlgeschlagen: {len(fail)}")
if fail:
    print("FEHLER:", fail)
    sys.exit(1)

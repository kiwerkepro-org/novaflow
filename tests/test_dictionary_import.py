"""Tests fuer den Vokabular-Import ins Woerterbuch (JJ, 2026-07-27).

Nutzt eine temporaere Datei statt der echten ~/.novaflow/dictionary.json,
indem die modul-globalen Pfade von utils.dictionary_store vor dem Anlegen
der Test-Instanz umgebogen werden.
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT + "/src")

import utils.dictionary_store as ds_module

tmp_dir = Path(tempfile.mkdtemp(prefix="novaflow_dict_test_"))
ds_module._DATA_DIR = tmp_dir
ds_module._DICT_FILE = tmp_dir / "dictionary.json"

parse_vocabulary_text = ds_module.parse_vocabulary_text
DictionaryStore = ds_module.DictionaryStore

ok = []
fail = []


def check(n, c):
    (ok if c else fail).append(n)
    print(("  OK   " if c else "  FEHL ") + n)


print("\n=== parse_vocabulary_text: Zeilenformen ===")
text = (
    "TensorFlow\n"
    "\n"
    "# das ist ein Kommentar\n"
    "nowa flow=NovaFlow\n"
    "flubar\ttabtrenner\n"
    "wisper -> Wispr\n"
    "komma,getrennt\n"
    "   \n"
    "  Kubernetes  \n"
)
pairs = parse_vocabulary_text(text)
check("Kommentare und Leerzeilen ignoriert", len(pairs) == 6)
check("einzelnes Wort -> spoken==correction", ("TensorFlow", "TensorFlow") in pairs)
check("= trennt spoken/correction", ("nowa flow", "NovaFlow") in pairs)
check("Tab trennt spoken/correction", ("flubar", "tabtrenner") in pairs)
check("-> trennt spoken/correction", ("wisper", "Wispr") in pairs)
check("Komma trennt spoken/correction", ("komma", "getrennt") in pairs)
check("Umgebende Leerzeichen werden entfernt", ("Kubernetes", "Kubernetes") in pairs)

print("\n=== DictionaryStore.import_entries ===")
store = DictionaryStore()
result = store.import_entries([("Kubernetes", "Kubernetes"), ("nowa flow", "NovaFlow")])
check("beide neuen Eintraege hinzugefuegt", result == {"added": 2, "skipped": 0})
check("Eintraege wirklich gespeichert", len(store.get_entries()) == 2)

result2 = store.import_entries([("kubernetes", "Kubernetes"), ("Docker", "Docker")])
check(
    "Duplikat (gross/klein egal) uebersprungen, neues hinzugefuegt",
    result2 == {"added": 1, "skipped": 1},
)
check("insgesamt 3 Eintraege nach zweitem Import", len(store.get_entries()) == 3)

result3 = store.import_entries([("", "leer"), ("valide", "")])
check("Paare mit leerer Seite werden verworfen", result3 == {"added": 0, "skipped": 0})
check("keine leeren Eintraege gelandet", len(store.get_entries()) == 3)

print("\n=== ERGEBNIS ===")
print(f"bestanden: {len(ok)}   fehlgeschlagen: {len(fail)}")
if fail:
    print("FEHLER:", fail)
    sys.exit(1)

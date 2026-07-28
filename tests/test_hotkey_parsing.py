"""Tests fuer die Tastenkombination-Erkennung in interface.py (JJ,
2026-07-28, Version 1.0.4: Undo-Hotkey). Deckt u.a. einen echten Bug ab, der
beim Bauen dieser Funktion auffiel: Funktionstasten wie "f6" wurden von
_parse_combo() gar nicht erkannt und fielen stillschweigend auf eine leere
Kombination zurueck - der Undo-Hotkey haette sich in diesem Fall einfach
nie ausgeloest, ohne jede Fehlermeldung. Betraf im alten Code (ohne die
_parse_combo-Verallgemeinerung) unbemerkt auch die schon vorher
angebotenen Hotkey-Optionen "f8"/"f9"/"f10" auf der Diktat-Seite.

Stubt pynput/sounddevice/soundfile komplett weg (in der Sandbox nicht
installiert, hier wird ausschliesslich reine Parsing-Logik gebraucht)."""
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _FakeKey:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"Key.{self.name}"


def _install_fake_pynput():
    pynput = types.ModuleType("pynput")
    keyboard_mod = types.ModuleType("pynput.keyboard")

    class Key:
        pass

    names = [
        "ctrl", "alt", "shift", "cmd", "alt_gr",
        "ctrl_l", "ctrl_r", "alt_l", "alt_r", "shift_l", "shift_r", "cmd_l", "cmd_r",
    ] + [f"f{i}" for i in range(1, 21)]
    for name in names:
        setattr(Key, name, _FakeKey(name))

    class KeyCode:
        def __init__(self, char=None):
            self.char = char

        @classmethod
        def from_char(cls, c):
            return cls(char=c)

        def __eq__(self, other):
            return isinstance(other, KeyCode) and self.char == other.char

        def __hash__(self):
            return hash(("KeyCode", self.char))

        def __repr__(self):
            return f"KeyCode({self.char!r})"

    class Listener:
        def __init__(self, *a, **k):
            pass

    keyboard_mod.Key = Key
    keyboard_mod.KeyCode = KeyCode
    keyboard_mod.Listener = Listener
    pynput.keyboard = keyboard_mod
    sys.modules["pynput"] = pynput
    sys.modules["pynput.keyboard"] = keyboard_mod
    sys.modules["sounddevice"] = types.ModuleType("sounddevice")
    sys.modules["soundfile"] = types.ModuleType("soundfile")

    utils = types.ModuleType("utils")
    utils.__path__ = []
    sys.modules["utils"] = utils
    log_mod = types.ModuleType("utils.logger")

    class _L:
        def __getattr__(self, n):
            return lambda *a, **k: None

    log_mod.logger = _L()
    sys.modules["utils.logger"] = log_mod

    cfg_mod = types.ModuleType("utils.config")

    class _Cfg:
        def get(self, k, d=None):
            return d

        def get_bool(self, k, d=False):
            return d

    cfg_mod.config = _Cfg()
    sys.modules["utils.config"] = cfg_mod

    plat_mod = types.ModuleType("platforms")

    class FakePlatform:
        name = "fake"

        def default_hotkey(self):
            return "ctrl_win"

        def paste_key(self):
            return Key.ctrl

    plat_mod.get_platform = lambda: FakePlatform()
    sys.modules["platforms"] = plat_mod

    return Key, KeyCode


Key, KeyCode = _install_fake_pynput()
sys.path.insert(0, ROOT + "/src")
import interface  # noqa: E402

ok = []
fail = []


def check(n, c):
    (ok if c else fail).append(n)
    print(("  OK   " if c else "  FEHL ") + n)


fi = interface.FlowInterface.__new__(interface.FlowInterface)

print("\n=== _parse_combo: Modifier-Kombinationen ===")
check("ctrl_win", fi._parse_combo("ctrl_win") == frozenset({Key.ctrl, Key.cmd}))
check("ctrl_cmd", fi._parse_combo("ctrl_cmd") == frozenset({Key.ctrl, Key.cmd}))
check("leerer String -> leere Kombination", fi._parse_combo("") == frozenset())
check("nur Leerzeichen -> leere Kombination", fi._parse_combo("   ") == frozenset())

print("\n=== _parse_combo: Undo-Hotkey mit normaler Taste (z.B. 'z') ===")
combo = fi._parse_combo("ctrl_alt_z")
check("ctrl_alt_z enthaelt Strg", Key.ctrl in combo)
check("ctrl_alt_z enthaelt Alt", Key.alt in combo)
check("ctrl_alt_z enthaelt die Taste 'z'", KeyCode.from_char("z") in combo)
check("ctrl_alt_z hat genau 3 Tasten", len(combo) == 3)

print("\n=== _parse_combo: Funktionstasten (Regressionstest) ===")
check("f6 wird als Key.f6 erkannt, NICHT als leere Kombination", fi._parse_combo("f6") == frozenset({Key.f6}))
check("f8 wird erkannt (betraf vorher auch den normalen Hotkey)", fi._parse_combo("f8") == frozenset({Key.f8}))
check("f10 wird erkannt", fi._parse_combo("f10") == frozenset({Key.f10}))

print("\n=== _parse_hotkey: leerer/unbekannter Fallback bleibt erhalten ===")
fi_default = interface.FlowInterface.__new__(interface.FlowInterface)
fi_default._active_hotkey_str = lambda: "irgendwas_unbekanntes"
check(
    "unbekannte Kombination faellt auf Alt Gr zurueck (kein leerer Hotkey)",
    fi_default._parse_hotkey() == frozenset({interface.keyboard.Key.alt_gr}),
)

print("\n=== ERGEBNIS ===")
print(f"bestanden: {len(ok)}   fehlgeschlagen: {len(fail)}")
if fail:
    print("FEHLER:", fail)
    sys.exit(1)

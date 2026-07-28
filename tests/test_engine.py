import sys, types, time, threading, importlib.util
import os
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),"fakeqt"))

# --- schwere Abhaengigkeiten wegstubben, wir testen nur EngineController ---
for name in ("ctranslate2", "faster_whisper"):
    sys.modules[name] = types.ModuleType(name)

utils = types.ModuleType("utils"); utils.__path__ = []
sys.modules["utils"] = utils
log_mod = types.ModuleType("utils.logger")
class _L:
    def error(self,*a,**k): print("   [logger.error]", a[0][:70])
    def warning(self,*a,**k): pass
    def info(self,*a,**k): pass
log_mod.logger = _L(); sys.modules["utils.logger"] = log_mod

cfg_mod = types.ModuleType("utils.config")
class _Cfg:
    def get(self, k, d=None): return d
    def get_bool(self, k, d=False): return d
    def set(self, k, v): pass
cfg_mod.config = _Cfg(); sys.modules["utils.config"] = cfg_mod
sec_mod = types.ModuleType("utils.secure_config")
class _Sec:
    def get(self, k, d=None): return d
    def set(self, k, v): return True
sec_mod.secure_config = _Sec(); sys.modules["utils.secure_config"] = sec_mod

upd = types.ModuleType("utils.update_checker")
CHECK_RESULT = {}
CHECK_DELAY = [0.0]
def check_for_update(*a, **k):
    time.sleep(CHECK_DELAY[0])
    assert threading.current_thread() is not threading.main_thread(), \
        "check_for_update lief im GUI-Thread!"
    return dict(CHECK_RESULT)
upd.check_for_update = check_for_update
sys.modules["utils.update_checker"] = upd

m = types.ModuleType("main")
class NovaFlowApp:
    def run(self): pass
    def stop(self): pass
m.NovaFlowApp = NovaFlowApp; sys.modules["main"] = m
g = types.ModuleType("gui_settings_modal")
g.NovaFlowSettingsModal = object; sys.modules["gui_settings_modal"] = g

# --- echtes novaflow.pyw laden ---
from importlib.machinery import SourceFileLoader
loader = SourceFileLoader("nf", ROOT + "/novaflow.pyw")
spec = importlib.util.spec_from_loader("nf", loader)
nf = importlib.util.module_from_spec(spec)
sys.modules["nf"] = nf
loader.exec_module(nf)

from PyQt6.QtCore import process_events, MAIN_THREAD
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon

app = QApplication([])
tray = QSystemTrayIcon()
ok = []; fail = []
def check(name, cond):
    (ok if cond else fail).append(name)
    print(("  OK   " if cond else "  FEHL ") + name)

print("\n=== 1) Update gefunden, Rueckruf im GUI-Thread? ===")
CHECK_RESULT.clear(); CHECK_RESULT.update(
    {"available": True, "latest_version": "0.5.6", "current_version": "0.5.5",
     "download_url": "http://x/Setup.exe"})
CHECK_DELAY[0] = 0.3
eng = nf.EngineController(tray)
got = []
eng.check_for_update_async(True, lambda info, manual: got.append(
    (info.get("latest_version"), manual, threading.current_thread())))
check("Rueckruf feuert NICHT sofort (GUI bleibt frei)", got == [])
t0 = time.time(); time.sleep(0.5)
check("Rueckruf feuert auch nach Wartezeit noch nicht ohne Ereignisschleife", got == [])
n = process_events()
check("Ereignisschleife hat genau die Zustellung abgearbeitet", n >= 1)
check("Rueckruf genau einmal aufgerufen", len(got) == 1)
check("richtige Version uebergeben", got and got[0][0] == "0.5.6")
check("manual-Flag korrekt durchgereicht", got and got[0][1] is True)
check("Rueckruf lief im GUI-Thread", got and got[0][2] is MAIN_THREAD)
check("pending_update gesetzt", eng.pending_update is not None)
check("keine Karteileiche in _check_callbacks", len(eng._check_callbacks) == 0)

print("\n=== 2) Kein Update vorhanden ===")
CHECK_RESULT.clear(); CHECK_RESULT.update({"available": False, "current_version": "0.5.6"})
CHECK_DELAY[0] = 0.0
eng2 = nf.EngineController(tray)
got2 = []
eng2.check_for_update_async(False, lambda i, mn: got2.append((i, mn)))
time.sleep(0.2); process_events()
check("Rueckruf aufgerufen", len(got2) == 1)
check("pending_update bleibt leer", eng2.pending_update is None)
check("_check_callbacks aufgeraeumt", len(eng2._check_callbacks) == 0)

print("\n=== 3) Zwei Pruefungen gleichzeitig, keine Verwechslung ===")
eng3 = nf.EngineController(tray)
r = []
CHECK_RESULT.clear(); CHECK_RESULT.update({"available": False, "current_version": "A"})
eng3.check_for_update_async(True, lambda i, mn: r.append(("erste", mn)))
eng3.check_for_update_async(False, lambda i, mn: r.append(("zweite", mn)))
time.sleep(0.3); process_events()
check("beide Rueckrufe kamen an", len(r) == 2)
check("manual-Flags nicht vertauscht",
      sorted(x[1] for x in r) == [False, True])
check("_check_callbacks vollstaendig leer", len(eng3._check_callbacks) == 0)

print("\n=== ERGEBNIS ===")
print(f"bestanden: {len(ok)}   fehlgeschlagen: {len(fail)}")
if fail: print("FEHLER:", fail); sys.exit(1)

import sys, types, time, threading, importlib.util
import os
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),"fakeqt"))
for name in ("ctranslate2", "faster_whisper"):
    sys.modules[name] = types.ModuleType(name)
utils = types.ModuleType("utils"); utils.__path__ = []; sys.modules["utils"] = utils
log_mod = types.ModuleType("utils.logger")
class _L:
    def error(self,*a,**k): print("   [logger.error]", str(a[0])[:60])
    def warning(self,*a,**k): pass
    def info(self,*a,**k): pass
log_mod.logger=_L(); sys.modules["utils.logger"]=log_mod
cfg_mod = types.ModuleType("utils.config")
class _Cfg:
    def get(self, k, d=None): return d
    def get_bool(self, k, d=False): return d
    def set(self, k, v): pass
cfg_mod.config=_Cfg(); sys.modules["utils.config"]=cfg_mod
sec_mod = types.ModuleType("utils.secure_config")
class _Sec:
    def get(self, k, d=None): return d
    def set(self, k, v): return True
sec_mod.secure_config=_Sec(); sys.modules["utils.secure_config"]=sec_mod
upd = types.ModuleType("utils.update_checker"); upd.check_for_update=lambda *a,**k:{}
sys.modules["utils.update_checker"]=upd
m=types.ModuleType("main")
class NovaFlowApp:
    stopped=[]
    def run(self): time.sleep(2)
    def stop(self): NovaFlowApp.stopped.append(1)
m.NovaFlowApp=NovaFlowApp; sys.modules["main"]=m
g=types.ModuleType("gui_settings_modal"); g.NovaFlowSettingsModal=object
sys.modules["gui_settings_modal"]=g

# --- gefaelschtes requests: steuerbarer Download ---
FAIL=[False]
req=types.ModuleType("requests")
class _Resp:
    def __enter__(self): return self
    def __exit__(self,*a): return False
    def raise_for_status(self):
        if FAIL[0]: raise Exception("HTTP 404 Not Found")
    def iter_content(self, chunk_size=0): return [b"MZ", b"data"]
def _get(url, stream=False, timeout=0):
    assert threading.current_thread() is not threading.main_thread(), \
        "Download lief im GUI-Thread!"
    return _Resp()
req.get=_get; sys.modules["requests"]=req

import subprocess
POPEN=[]
subprocess.Popen = lambda args, *a, **k: POPEN.append(args)

sys.platform = "win32"
from importlib.machinery import SourceFileLoader
loader = SourceFileLoader("nf",ROOT + "/novaflow.pyw")
spec = importlib.util.spec_from_loader("nf", loader)
nf = importlib.util.module_from_spec(spec); sys.modules["nf"]=nf
loader.exec_module(nf)

from PyQt6.QtCore import process_events, MAIN_THREAD
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon
app=QApplication([]); tray=QSystemTrayIcon()
ok=[];fail=[]
def check(n,c):
    (ok if c else fail).append(n); print(("  OK   " if c else "  FEHL ")+n)

INFO={"available":True,"latest_version":"0.5.6","download_url":"http://x/Setup.exe",
      "release_url":"http://x"}

print("\n=== 4) Download erfolgreich -> Installer starten + beenden ===")
FAIL[0]=False; POPEN.clear(); NovaFlowApp.stopped.clear()
eng=nf.EngineController(tray); eng.start(); time.sleep(0.1)
prog=[]; errs=[]
eng.install_update(INFO, on_progress=prog.append, on_error=errs.append)
check("Fortschrittsmeldung sofort (synchron) gezeigt", len(prog)==1)
check("Installer noch NICHT gestartet (laeuft im Hintergrund)", POPEN==[])
time.sleep(0.3); process_events()
check("Installer genau einmal gestartet", len(POPEN)==1)
check("Installer-Pfad zeigt auf NovaFlow-Setup.exe",
      POPEN and "NovaFlow-Setup.exe" in str(POPEN[0][0]))
check("Update-Installer laeuft still (/VERYSILENT), kein Assistent noetig",
      POPEN and "/VERYSILENT" in POPEN[0])
check("/SUPPRESSMSGBOXES gesetzt (keine Nachfragen im Stillen)",
      POPEN and "/SUPPRESSMSGBOXES" in POPEN[0])
check("/NORESTART gesetzt (kein ungefragter Windows-Neustart)",
      POPEN and "/NORESTART" in POPEN[0])
check("kein Fehler-Rueckruf", errs==[])
check("Diktier-Motor sauber gestoppt", len(NovaFlowApp.stopped)>=1)
check("Anwendung beendet (app.quit)", app.quit_called is True)
check("_download_handlers aufgeraeumt", len(eng._download_handlers)==0)

print("\n=== 5) Download schlaegt fehl -> Fehler melden, NICHT beenden ===")
FAIL[0]=True; POPEN.clear()
app.quit_called=False
eng2=nf.EngineController(tray)
prog2=[]; errs2=[]
eng2.install_update(INFO, on_progress=prog2.append, on_error=errs2.append)
time.sleep(0.3); process_events()
check("Fehler-Rueckruf genau einmal", len(errs2)==1)
check("Fehlertext durchgereicht", errs2 and "404" in errs2[0])
check("Installer NICHT gestartet", POPEN==[])
check("Anwendung NICHT beendet", app.quit_called is False)
check("_download_handlers aufgeraeumt", len(eng2._download_handlers)==0)

print("\n=== 6) Nicht-Windows -> Browser statt stillem Ersatz ===")
sys.platform="darwin"; nf.sys.platform="darwin"
import webbrowser
opened=[]; webbrowser.open=lambda u: opened.append(u)
eng3=nf.EngineController(tray)
eng3.install_update(INFO)
check("Release-Seite im Browser geoeffnet", opened==["http://x"])
check("kein Download-Thread gestartet", len(eng3._download_handlers)==0)

print("\n=== ERGEBNIS ===")
print(f"bestanden: {len(ok)}   fehlgeschlagen: {len(fail)}")
if fail: print("FEHLER:",fail); sys.exit(1)

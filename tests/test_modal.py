import ast, sys, types
import os
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = ROOT + "/src/gui_settings_modal.py"
src = open(SRC, encoding="utf-8").read()
tree = ast.parse(src)

cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
want = {"_check_for_update_clicked", "_on_update_check_result",
        "_install_update_clicked", "_open_release_page"}
methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in want]
assert len(methods) == 4, f"nur gefunden: {[m.name for m in methods]}"

ns = {"COLORS": {"danger":"#f00","text_muted":"#888","cyan_neon":"#0eb","off_white":"#fff"}}
mod = ast.Module(body=methods, type_ignores=[])
exec(compile(mod, SRC, "exec"), ns)

class FakeBtn:
    def __init__(s): s.enabled=True; s.visible=True; s.text=""
    def setEnabled(s,v): s.enabled=v
    def setVisible(s,v): s.visible=v
    def setText(s,t): s.text=t
class FakeLbl:
    def __init__(s): s.text=""; s.style=""
    def setText(s,t): s.text=t
    def setStyleSheet(s,v): s.style=v
class FakeEngine:
    def __init__(s): s.pending_update=None; s.calls=[]; s.installed=[]
    def check_for_update_async(s, manual, cb): s.calls.append((manual,cb))
    def install_update(s, info, on_progress=None, on_error=None):
        s.installed.append(info); s._prog=on_progress; s._err=on_error
class S: pass
for _n in ("_check_for_update_clicked","_on_update_check_result",
           "_install_update_clicked","_open_release_page"):
    setattr(S, _n, ns[_n])

def fresh(engine=True):
    s=S(); s.engine_api=FakeEngine() if engine else None
    s.check_update_btn=FakeBtn(); s.install_update_btn=FakeBtn()
    s.update_status_label=FakeLbl(); s.installed_version_label=FakeLbl()
    s.install_update_btn.visible=False
    return s

ok=[];fail=[]
def check(n,c):
    (ok if c else fail).append(n); print(("  OK   " if c else "  FEHL ")+n)

print("\n=== 7) Klick auf 'Nach Updates suchen' ===")
s=fresh()
ns["_check_for_update_clicked"](s)
check("Knopf gesperrt (kein Mehrfachklick)", s.check_update_btn.enabled is False)
check("Knopftext zeigt Suchlauf", "Suche" in s.check_update_btn.text)
check("Statuszeile informiert den Nutzer", s.update_status_label.text != "")
check("Pruefung an die Engine delegiert (nicht blockierend)", len(s.engine_api.calls)==1)
check("als manuelle Pruefung markiert", s.engine_api.calls[0][0] is True)

print("\n=== 8) Ohne Engine-Verbindung: sauberer Hinweis statt Absturz ===")
s2=fresh(engine=False)
ns["_check_for_update_clicked"](s2)
check("kein Absturz, Hinweistext gesetzt", "nicht verfügbar" in s2.update_status_label.text)

print("\n=== 9) Ergebnis: Update verfuegbar ===")
s3=fresh()
ns["_on_update_check_result"](s3, {"available":True,"latest_version":"0.5.6",
                                   "current_version":"0.5.5","release_url":"u"}, True)
check("Suchknopf wieder benutzbar", s3.check_update_btn.enabled is True)
check("Installieren-Knopf sichtbar", s3.install_update_btn.visible is True)
check("Installieren-Knopf nennt die Version", "0.5.6" in s3.install_update_btn.text)
check("Text verweist NICHT mehr aufs Tray-Menue",
      "Tray" not in s3.update_status_label.text)
check("installierte Version aktualisiert", "0.5.5" in s3.installed_version_label.text)

print("\n=== 10) Ergebnis: aktuell / Fehler ===")
s4=fresh(); ns["_on_update_check_result"](s4,{"available":False,"current_version":"0.5.6"},True)
check("Installieren-Knopf bleibt verborgen", s4.install_update_btn.visible is False)
check("Meldung 'ist aktuell'", "aktuell" in s4.update_status_label.text)
s5=fresh(); ns["_on_update_check_result"](s5,{"available":False,"error":"kein Netz"},True)
check("Fehler sichtbar gemeldet", "fehlgeschlagen" in s5.update_status_label.text)
check("Installieren-Knopf bei Fehler verborgen", s5.install_update_btn.visible is False)

print("\n=== 11) Klick auf 'Update installieren' ===")
s6=fresh(); s6.engine_api.pending_update={"latest_version":"0.5.6"}
ns["_install_update_clicked"](s6)
check("Installation angestossen", len(s6.engine_api.installed)==1)
check("beide Knoepfe gesperrt (kein Doppelklick)",
      s6.install_update_btn.enabled is False and s6.check_update_btn.enabled is False)
s6.engine_api._err("Netzwerk weg")
check("Fehler entsperrt die Knoepfe wieder",
      s6.install_update_btn.enabled is True and s6.check_update_btn.enabled is True)
check("Fehlertext im Fenster", "Netzwerk weg" in s6.update_status_label.text)

s7=fresh(); s7.engine_api.pending_update=None
ns["_install_update_clicked"](s7)
check("ohne gefundenes Update passiert nichts", len(s7.engine_api.installed)==0)

print("\n=== ERGEBNIS ===")
print(f"bestanden: {len(ok)}   fehlgeschlagen: {len(fail)}")
if fail: print("FEHLER:",fail); sys.exit(1)

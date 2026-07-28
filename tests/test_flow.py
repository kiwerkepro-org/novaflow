import sys, types, threading, os
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
utils=types.ModuleType("utils"); utils.__path__=[]; sys.modules["utils"]=utils
lg=types.ModuleType("utils.logger")
class _L:
    def __getattr__(s,n): return lambda *a,**k: None
lg.logger=_L(); sys.modules["utils.logger"]=lg

CFG={}
cf=types.ModuleType("utils.config")
class _C:
    def get(s,k,d=None): return CFG.get(k,d)
    def get_bool(s,k,d=False):
        v=CFG.get(k,d)
        if isinstance(v,bool): return v
        if isinstance(v,str): return v.strip().lower() in ("1","true","yes","on")
        return bool(v)
cf.config=_C(); sys.modules["utils.config"]=cf

SEC={}
sc=types.ModuleType("utils.secure_config")
class _S:
    def get(s,k,d=None): return SEC.get(k,d)
sc.secure_config=_S(); sys.modules["utils.secure_config"]=sc

for n,attr,val in [("utils.style_store","style_store",None),
                   ("utils.dictionary_store","dictionary_store",None),
                   ("utils.feedback_store","feedback_store",None)]:
    mm=types.ModuleType(n)
    class _X:
        def get_style(s): return {"category":"work","tone":"formal"}
        def get_entries(s): return []
        def get_correction_count(s): return 0
        def get_best_examples(s,n=3): return []
    setattr(mm,attr,_X()); sys.modules[n]=mm
mm=types.ModuleType("utils.style_store"); 
class _Y:
    def get_style(s): return {"category":"work","tone":"formal"}
mm.style_store=_Y(); mm.CATEGORIES={}; mm.TONES={}; sys.modules["utils.style_store"]=mm

tp=types.ModuleType("text_processor")
class TextProcessor:
    def __init__(s,language="de"): pass
    def process(s,t): return t
    # Absatzbildung (JJ, 2026-07-28, siehe flow.NovaFlowProcessor.refine_text):
    # hier als reiner Durchreicher gestubbt, echtes Verhalten wird separat in
    # text_processor.py getestet, nicht hier (dieser Test prueft nur die
    # Provider-Auswahl/den Rohtext-Modus).
    def insert_paragraph_breaks(s,t): return t
tp.TextProcessor=TextProcessor; sys.modules["text_processor"]=tp
pl=types.ModuleType("platforms"); pl.get_platform=lambda: None
sys.modules["platforms"]=pl

sys.path.insert(0,ROOT + "/src")
import flow

ok=[];fail=[]
def check(n,c):
    (ok if c else fail).append(n); print(("  OK   " if c else "  FEHL ")+n)

print("\n=== 12) Provider-Auswahl ===")
CFG.clear(); SEC.clear()
CFG["LLM_PROVIDER"]="openrouter"; SEC["OPENROUTER_API_KEY"]="sk-or-test"
p=flow.NovaFlowProcessor()
check("openrouter wird gewaehlt", isinstance(p.active_provider, flow.OpenRouterProvider))

CFG["LLM_PROVIDER"]="ionos"; SEC["IONOS_API_KEY"]="ionos-test"
p=flow.NovaFlowProcessor()
check("ionos wird gewaehlt", isinstance(p.active_provider, flow.IonosProvider))

CFG["LLM_PROVIDER"]="disabled"
p=flow.NovaFlowProcessor()
check("disabled wird gewaehlt (Index 3 stimmt!)",
      isinstance(p.active_provider, flow.DisabledProvider))

CFG["LLM_PROVIDER"]="ionos"; SEC.pop("IONOS_API_KEY")
p=flow.NovaFlowProcessor()
check("ionos ohne Key -> Rueckfall, kein Absturz",
      not isinstance(p.active_provider, flow.IonosProvider))
check("Rueckfall landet auf openrouter (Key vorhanden)",
      isinstance(p.active_provider, flow.OpenRouterProvider))

CFG["LLM_PROVIDER"]="ollama"; SEC.clear()
p=flow.NovaFlowProcessor()
check("gar keine Keys -> DisabledProvider statt Absturz",
      p.active_provider.is_available() is True)

print("\n=== 13) IonosProvider Verhalten ===")
SEC["IONOS_API_KEY"]="k"; CFG["IONOS_MODEL"]="mistralai/Mistral-Small-24B-Instruct"
ip=flow.IonosProvider()
check("is_available mit Key", ip.is_available() is True)
check("EU-Endpunkt (Deutschland)", "de-txl.ionos.com" in ip.BASE_URL)
check("Name zeigt Modell", "Mistral-Small-24B-Instruct" in ip.get_name())

req=types.ModuleType("requests"); CAP={}
class _R:
    status_code=200
    def json(s): return {"choices":[{"message":{"content":"Korrigierter Text."}}]}
def _post(url, headers=None, json=None, timeout=None):
    CAP["url"]=url; CAP["headers"]=headers; CAP["json"]=json
    return _R()
req.post=_post; sys.modules["requests"]=req
out=ip.refine_text("korrigierter text")
check("Text verfeinert zurueck", out=="Korrigierter Text.")
check("richtiger Endpfad", CAP["url"].endswith("/chat/completions"))
check("Bearer-Token gesetzt", CAP["headers"]["Authorization"]=="Bearer k")
check("Modell mitgeschickt", CAP["json"]["model"]=="mistralai/Mistral-Small-24B-Instruct")

class _RB(_R):
    status_code=500
    def json(s): return {}
req.post=lambda *a,**k: _RB()
check("HTTP-Fehler -> Originaltext, kein Absturz",
      ip.refine_text("mein text")=="mein text")

def _boom(*a,**k): raise Exception("Netzwerk weg")
req.post=_boom
check("Netzwerkfehler -> Originaltext, kein Absturz",
      ip.refine_text("mein text")=="mein text")

class _RH(_R):
    def json(s): return {"choices":[{"message":{"content":"X"*500}}]}
req.post=lambda *a,**k: _RH()
check("Halluzination (viel zu lang) -> Originaltext",
      ip.refine_text("kurz")=="kurz")

ip2=flow.IonosProvider.__new__(flow.IonosProvider)
ip2.api_key=None; ip2.model="m"
check("ohne Key -> Text unveraendert durchgereicht",
      ip2.refine_text("unveraendert")=="unveraendert")

print("\n=== 14) Rohtext-Modus (Tray-Schnellumschaltung) ===")
CFG.clear(); SEC.clear()
CFG["LLM_PROVIDER"]="disabled"; CFG["RAW_TEXT_MODE"]="true"
p=flow.NovaFlowProcessor()

class _BoomProvider:
    def refine_text(s, t): raise AssertionError("Veredelung haette uebersprungen werden muessen")
    def is_available(s): return True
    def get_name(s): return "boom"
p.active_provider=_BoomProvider()

check("RAW_TEXT_MODE=='true' (String aus .env) ueberspringt die Veredelung",
      p.refine_text("ein laengerer beispieltext mit mehr als zehn woertern zum testen")
      == "ein laengerer beispieltext mit mehr als zehn woertern zum testen")

CFG["RAW_TEXT_MODE"]=True
check("RAW_TEXT_MODE als echter bool funktioniert genauso",
      p.refine_text("noch ein laengerer beispieltext mit mehr als zehn woertern")
      == "noch ein laengerer beispieltext mit mehr als zehn woertern")

CFG["RAW_TEXT_MODE"]="false"
called=[]
p.active_provider=type("P",(),{"refine_text":lambda s,t: called.append(t) or "veredelt"})()
check("RAW_TEXT_MODE aus -> Veredelung laeuft wie gewohnt",
      p.refine_text("ein laengerer beispieltext mit mehr als zehn woertern zum testen")=="veredelt")
check("Provider wurde dafuer tatsaechlich aufgerufen", len(called)==1)

print("\n=== ERGEBNIS ===")
print(f"bestanden: {len(ok)}   fehlgeschlagen: {len(fail)}")
if fail: print("FEHLER:",fail); sys.exit(1)

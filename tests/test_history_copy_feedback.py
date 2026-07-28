import ast, sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = ROOT + "/src/gui_settings_modal.py"
src = open(SRC, encoding="utf-8").read()
tree = ast.parse(src)

cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
want = {"_copy_history_entry", "_flash_history_feedback"}
methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in want]
assert len(methods) == 2, f"nur gefunden: {[m.name for m in methods]}"

ns = {"COLORS": {"danger": "#f00", "cyan_neon": "#0eb"}}


class FakeQTimer:
    """Faengt QTimer.singleShot() ab, statt wirklich zu warten. Der Test
    ruft die Callback selbst auf, wenn er das Verstreichen der Zeit
    simulieren will."""
    last_delay = None
    last_callback = None

    @staticmethod
    def singleShot(delay, callback):
        FakeQTimer.last_delay = delay
        FakeQTimer.last_callback = callback


ns["QTimer"] = FakeQTimer


class _FakeItemDataRole:
    UserRole = "UserRole"


class FakeQt:
    ItemDataRole = _FakeItemDataRole


ns["Qt"] = FakeQt

mod = ast.Module(body=methods, type_ignores=[])
exec(compile(mod, SRC, "exec"), ns)


class FakeItem:
    def __init__(s, text):
        s._text = text
    def data(s, role):
        return s._text


class FakeHistoryList:
    def __init__(s, current=None):
        s._current = current
    def currentItem(s):
        return s._current


class FakeClipboard:
    def __init__(s):
        s.written = []
    def write_text(s, text):
        s.written.append(text)


class FakePlatform:
    def __init__(s):
        s.clipboard = FakeClipboard()


class FakeLbl:
    def __init__(s):
        s.text = ""
        s.style = ""
    def setText(s, t):
        s.text = t
    def setStyleSheet(s, v):
        s.style = v


class S:
    pass


for _n in ("_copy_history_entry", "_flash_history_feedback"):
    setattr(S, _n, ns[_n])


def fresh(selected_text=None):
    s = S()
    s.platform = FakePlatform()
    s.history_list = FakeHistoryList(FakeItem(selected_text) if selected_text is not None else None)
    s.history_copy_feedback = FakeLbl()
    return s


ok = []
fail = []


def check(n, c):
    (ok if c else fail).append(n)
    print(("  OK   " if c else "  FEHL ") + n)


print("\n=== Eintrag ausgewaehlt: kopiert + Rueckmeldung ===")
s = fresh(selected_text="Hallo Welt")
ns["_copy_history_entry"](s)
check("Text landet in der Zwischenablage", s.platform.clipboard.written == ["Hallo Welt"])
check("Rueckmeldungstext gesetzt", s.history_copy_feedback.text == "In die Zwischenablage kopiert")
check("Timer zum Ausblenden gestellt", FakeQTimer.last_callback is not None)
FakeQTimer.last_callback()
check("Rueckmeldung blendet nach Timer wieder aus", s.history_copy_feedback.text == "")

print("\n=== Kein Eintrag ausgewaehlt: Hinweis statt stillem Nichtstun ===")
s2 = fresh(selected_text=None)
ns["_copy_history_entry"](s2)
check("nichts wird kopiert", s2.platform.clipboard.written == [])
check("Warnhinweis wird angezeigt", "auswaehlen" in s2.history_copy_feedback.text)

print("\n=== ERGEBNIS ===")
print(f"bestanden: {len(ok)}   fehlgeschlagen: {len(fail)}")
if fail:
    print("FEHLER:", fail)
    sys.exit(1)

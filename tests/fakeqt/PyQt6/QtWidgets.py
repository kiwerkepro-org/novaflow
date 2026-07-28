from PyQt6.QtCore import QObject
_APP = None
class QApplication(QObject):
    def __init__(self, argv=None):
        super().__init__()
        global _APP; _APP = self
        self.quit_called = False
    @staticmethod
    def instance(): return _APP
    def quit(self): self.quit_called = True
    def setQuitOnLastWindowClosed(self, v): pass
    def style(self): return None
    def exec(self): return 0
class QSystemTrayIcon(QObject):
    class MessageIcon:
        Information = 1; Warning = 2; Critical = 3
    class ActivationReason:
        Trigger = 1
    def __init__(self, *a): super().__init__()
    def setToolTip(self, t): pass
    def show(self): pass
    def showMessage(self, *a): pass
    def setContextMenu(self, m): pass
class QMenu(QObject): pass
class QStyle:
    class StandardPixmap:
        SP_ComputerIcon = 1
class QWidget(QObject):
    """Minimaler Stub, nur damit novaflow.pyw (FlowbarOverlay) importierbar
    bleibt. Die Tests hier pruefen EngineController/Update-Logik, nicht die
    tatsaechliche Flowbar-Anzeige (die braucht ein echtes Display)."""
    def __init__(self, *a, **k): super().__init__()
    def setAttribute(self, *a, **k): pass
    def resize(self, *a, **k): pass
    def move(self, *a, **k): pass
    def show(self): pass
    def hide(self): pass
    def update(self): pass
    def rect(self): return None

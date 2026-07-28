from PyQt6.QtCore import QObject
class QIcon(QObject):
    def __init__(self, *a): super().__init__()
class QAction(QObject):
    def __init__(self, *a): super().__init__()
# Minimale Stubs, nur damit novaflow.pyw (FlowbarOverlay) importierbar
# bleibt, siehe gleiche Begruendung in QtWidgets.py.
class QPainter:
    def __init__(self, *a, **k): pass
    def setRenderHint(self, *a, **k): pass
    def setPen(self, *a, **k): pass
    def setBrush(self, *a, **k): pass
    def drawRoundedRect(self, *a, **k): pass
    def end(self): pass
class QColor:
    def __init__(self, *a, **k): pass
class QGuiApplication:
    @staticmethod
    def primaryScreen(): return None

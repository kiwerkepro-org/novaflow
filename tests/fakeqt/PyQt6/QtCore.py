"""Minimaler Qt-Nachbau, der NUR die Thread-/Signal-Semantik abbildet,
um die echte EngineController-Logik ausfuehren zu koennen."""
import threading, queue

MAIN_THREAD = threading.current_thread()
EVENT_QUEUE = queue.Queue()

class _ConnType:
    QueuedConnection = "queued"
    AutoConnection = "auto"

class Qt:
    ConnectionType = _ConnType

class _BoundSignal:
    def __init__(self, owner):
        self.owner = owner
        self.slots = []
    def connect(self, slot, conn=_ConnType.AutoConnection):
        self.slots.append((slot, conn))
    def emit(self, *args):
        for slot, conn in list(self.slots):
            if conn == _ConnType.QueuedConnection:
                # wie Qt: NICHT sofort ausfuehren, sondern in die
                # Ereigniswarteschlange des GUI-Threads legen
                EVENT_QUEUE.put((slot, args, self.owner))
            else:
                _dispatch(slot, args, self.owner)

def _dispatch(slot, args, sender):
    recv = getattr(slot, "__self__", None)
    if isinstance(recv, QObject):
        recv._current_sender = sender
    try:
        slot(*args)
    finally:
        if isinstance(recv, QObject):
            recv._current_sender = None

def process_events():
    """Simuliert app.exec(): arbeitet die Warteschlange im GUI-Thread ab."""
    assert threading.current_thread() is MAIN_THREAD
    n = 0
    while not EVENT_QUEUE.empty():
        slot, args, sender = EVENT_QUEUE.get()
        _dispatch(slot, args, sender)
        n += 1
    return n

class pyqtSignal:
    def __init__(self, *types):
        self.types = types
        self.name = None
    def __set_name__(self, owner, name):
        self.name = name
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        store = obj.__dict__.setdefault("_signals", {})
        if self.name not in store:
            store[self.name] = _BoundSignal(obj)
        return store[self.name]

class QObject:
    def __init__(self, parent=None):
        self._parent = parent
        self._current_sender = None
        self._thread = threading.current_thread()
    def sender(self):
        return self._current_sender
    def thread(self):
        return self._thread
    def deleteLater(self):
        pass

class QThread(QObject):
    finished = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self._t = None
    def start(self):
        def _runner():
            try:
                self.run()
            finally:
                self.finished.emit()
        self._t = threading.Thread(target=_runner, daemon=True)
        self._t.start()
    def isRunning(self):
        return self._t is not None and self._t.is_alive()
    def wait(self, *a):
        if self._t: self._t.join(timeout=5)
    def run(self):
        pass

class QSharedMemory(QObject):
    def __init__(self, key): super().__init__()
    def create(self, n): return True

class QTimer(QObject):
    timeout = pyqtSignal()
    def start(self, ms=0): pass
    @staticmethod
    def singleShot(ms, fn): pass

class QSize:
    def __init__(self, *a): pass

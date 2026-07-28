#!/usr/bin/env python3
"""
NovaFlow Launcher (Next)
Startet NovaFlow als eigenstaendige Tray-Anwendung – EIN Prozess.

Bewusst anders als im bisherigen NovaFlow (C:\\KIW-SCHMIEDE\\NOVA-FLOW): dort
startete launcher_pro.py den eigentlichen Diktier-Motor als eigenen
Kindprozess (subprocess.Popen mit [sys.executable, "src/main.py"]). Das
funktioniert nicht mehr, sobald NovaFlow als PyInstaller-/py2app-Anwendung
gebuendelt ist, dann gibt es weder eine lose main.py-Datei noch einen
separaten Python-Interpreter, den man aufrufen koennte. Deshalb laeuft der
Motor hier von Anfang an in einem Hintergrund-Thread IM SELBEN Prozess wie
die Tray-Oberflaeche, das ist sowohl im normalen Python-Betrieb als auch
gebuendelt gueltig.

Die volle Einstellungen-Oberflaeche (Woerterbuch, Ausschnitte, Schreibstil,
Notizbuch, Verlauf, technische Einstellungen) liegt in gui_settings_modal.py
und wird ueber den Tray-Menuepunkt "Einstellungen" geoeffnet.
"""
import sys
import os
from pathlib import Path

project_root = Path(__file__).resolve().parent
os.chdir(project_root)
sys.path.insert(0, str(project_root / "src"))

# Versteckter Aufruf, den NUR der Deinstaller (installer.iss, [UninstallRun])
# benutzt: raeumt die im Windows Credential Manager / macOS Schluesselbund
# gespeicherten API-Keys auf, BEVOR die Programmdateien geloescht werden.
# Absichtlich VOR den schweren ctranslate2/PyQt6-Importen abgefangen und
# sofort beendet, damit die Deinstallation nicht unnoetig die ganze
# Spracherkennung mitladen muss.
if "--cleanup-uninstall" in sys.argv:
    from utils.secure_config import SecureConfig

    for _field in SecureConfig.SENSITIVE_FIELDS:
        SecureConfig.delete(_field)
    sys.exit(0)

# KRITISCH: ctranslate2 VOR PyQt6 importieren (verhindert Access Violation unter Windows,
# siehe gleiche Reihenfolge im bisherigen NovaFlow)
import ctranslate2  # noqa: E402,F401
import faster_whisper  # noqa: E402,F401

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QStyle, QWidget  # noqa: E402
from PyQt6.QtCore import QThread, pyqtSignal, QSharedMemory, QTimer, Qt, QObject  # noqa: E402
from PyQt6.QtGui import QIcon, QAction, QPainter, QColor, QGuiApplication  # noqa: E402

# WICHTIG: alle Signale, die aus einem Hintergrund-QThread kommen
# (EngineThread, UpdateCheckThread), werden unten IMMER mit ausdruecklichem
# Qt.ConnectionType.QueuedConnection verbunden. Grund: PyQt kann die
# Ziel-Thread-Zugehoerigkeit eines Slots nur zuverlaessig bestimmen, wenn
# der Slot eine gebundene Methode eines QObject ist. Bei einer einfachen
# verschachtelten Funktion oder einem Lambda (wie hier durchgaengig
# verwendet) gibt es kein QObject, dessen thread() PyQt abfragen koennte,
# und die automatische Verbindung faellt dann auf eine DIREKTE Verbindung
# zurueck: der Slot laeuft im SENDENDEN Hintergrund-Thread, nicht in der
# Qt-Oberflaeche. Werden darin Tray-/Menu-Objekte veraendert (setVisible,
# setText, showMessage), ist das eine Verletzung von Qts Regel "GUI-Objekte
# nur im GUI-Thread anfassen" und kann die Oberflaeche unbemerkt einfrieren,
# genau das ist am 2026-07-25 nach der ersten "Update verfuegbar"-Meldung
# passiert (Rechtsklick und Linksklick auf das Tray-Symbol reagierten nicht
# mehr, das laufende Diktat lief trotzdem weiter, weil es komplett getrennt
# vom Qt-Hauptthread laeuft).
QUEUED = Qt.ConnectionType.QueuedConnection

from utils.logger import logger  # noqa: E402
from utils.config import config  # noqa: E402
from utils.secure_config import secure_config  # noqa: E402
from utils.update_checker import check_for_update  # noqa: E402
from main import NovaFlowApp  # noqa: E402
from gui_settings_modal import NovaFlowSettingsModal  # noqa: E402

SINGLE_INSTANCE_KEY = "NovaFlow_SingleInstance_KIWERKE_NEXT"

# Alle 6 Stunden nach einer neueren Version schauen. Kein aggressiveres
# Intervall noetig, ein neues Release kommt nicht minuetlich.
UPDATE_CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000


class UpdateCheckThread(QThread):
    """Fragt im Hintergrund die GitHub-Releases-API ab, damit die
    Netzwerk-Anfrage die Tray-Oberflaeche nicht blockiert.

    Das Flag "manual" unterscheidet, ob der Nutzer die Pruefung selbst
    angestossen hat. Eine automatische Pruefung meldet sich nur, wenn es
    wirklich etwas Neues gibt, sonst waere sie alle sechs Stunden laestig.
    Eine manuelle Pruefung meldet dagegen IMMER ein Ergebnis, auch "alles
    aktuell" oder einen Fehler, sonst weiss der Nutzer nach dem Klick nicht,
    ob ueberhaupt etwas passiert ist.
    """

    finished_check = pyqtSignal(dict, bool)

    def __init__(self, manual: bool = False, parent=None):
        super().__init__(parent)
        self.manual = manual

    def run(self):
        try:
            result = check_for_update()
        except Exception as e:
            result = {"available": False, "error": str(e)}
        self.finished_check.emit(result, self.manual)


class UpdateDownloadThread(QThread):
    """Laedt die neue Setup.exe im Hintergrund.

    Vorher lief dieser Download (teils mehrere zehn MB) direkt im
    triggered-Slot des Tray-Menuepunkts, also blockierend im Qt-Hauptthread.
    Das war der zweite, eng verwandte Grund fuer eingefrorene Oberflaeche
    beim Aktualisieren (der erste war die ebenso blockierende Pruefung in
    UpdateCheckThread, siehe dort). Genau wie dort: Download im
    Hintergrund-Thread, Ergebnis per Signal mit QueuedConnection zurueck.
    """

    finished_download = pyqtSignal(str, str)  # (installer_path, error_message)

    def __init__(self, download_url: str, parent=None):
        super().__init__(parent)
        self.download_url = download_url

    def run(self):
        try:
            import tempfile
            import requests as _requests

            tmp_dir = Path(tempfile.gettempdir())
            installer_path = tmp_dir / "NovaFlow-Setup.exe"
            with _requests.get(self.download_url, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                with open(installer_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 256):
                        f.write(chunk)
            self.finished_download.emit(str(installer_path), "")
        except Exception as e:
            self.finished_download.emit("", str(e))


class FlowbarOverlay(QWidget):
    """Flowbar (JJ, 2026-07-28): sichtbare Pegelanzeige am unteren
    Bildschirmrand, solange NovaFlow aufnimmt. Vorher war die einzige
    Rueckmeldung dafuer die Audio-Stummschaltung, kein sichtbares Zeichen,
    dass gerade etwas passiert (die Idee dazu stand schon laenger auf der
    To-Do-Liste, siehe NOVA-FLOW-NEXT_Ideen-und-ToDo-Liste.md, der Name
    "Flowbar" wurde im Woerterbuch/text_processor.py schon vorher als
    Fehlerkennung abgefangen, obwohl es noch keine echte Anzeige dazu gab).

    Randlos, immer im Vordergrund, KEIN Taskbar-/Alt-Tab-Eintrag
    (Qt.WindowType.Tool), reagiert auf keine Klicks (die Maus soll immer
    zum darunterliegenden Fenster durchgereicht werden). Positioniert sich
    unten mittig auf dem primaeren Bildschirm.

    Mac-Hinweis (JJ, 2026-07-28): NovaFlow laeuft unter macOS bewusst
    fensterlos in der Menueleiste, ein zusaetzliches sichtbares Fenster ist
    dort Neuland und noch NICHT auf einem echten Mac getestet (siehe
    "Echten Test auf einem echten Mac-Geraet abwarten" in der To-Do-Liste).
    """

    WIDTH = 220
    HEIGHT = 14
    BOTTOM_MARGIN = 56
    # RMS-Referenzwert (float32-Samples, -1.0..1.0) fuer "volle Balkenbreite".
    # Normale Sprechlautstaerke liegt grob bei 0.03-0.15, eine 1:1-Skalierung
    # zum theoretischen Maximum (1.0) wuerde den Balken bei normaler
    # Sprache kaum sichtbar bewegen.
    LEVEL_REFERENCE = 0.12

    def __init__(self):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.resize(self.WIDTH, self.HEIGHT)
        self._level = 0.0

    def show_and_reset(self):
        """Slot fuer OverlayBridge.show_requested (siehe dort)."""
        self._level = 0.0
        self._position_bottom_center()
        self.show()
        self.update()

    def _position_bottom_center(self):
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return
        avail = screen.availableGeometry()
        x = avail.left() + (avail.width() - self.WIDTH) // 2
        y = avail.top() + avail.height() - self.HEIGHT - self.BOTTOM_MARGIN
        self.move(x, y)

    def set_level(self, rms: float):
        """Slot fuer OverlayBridge.level_changed (siehe dort)."""
        level = max(0.0, min(1.0, rms / self.LEVEL_REFERENCE))
        # Leichtes Glaetten, damit der Balken nicht bei jedem einzelnen
        # Audio-Block (alle ~256ms bei blocksize=4096/16kHz) hart
        # hin- und herspringt.
        self._level = self._level * 0.5 + level * 0.5
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg_rect = self.rect()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(10, 15, 26, 210))  # deep_navy, halbtransparent
        painter.drawRoundedRect(bg_rect, self.HEIGHT / 2, self.HEIGHT / 2)

        bar_rect = bg_rect.adjusted(2, 2, -2, -2)
        bar_rect.setWidth(max(0, int(bar_rect.width() * self._level)))
        painter.setBrush(QColor(0, 224, 184))  # cyan_neon
        painter.drawRoundedRect(bar_rect, max(0, (self.HEIGHT - 4) // 2), max(0, (self.HEIGHT - 4) // 2))

        painter.end()


class OverlayBridge(QObject):
    """Verbindet die Flowbar-Anzeige (lebt im GUI-Thread) mit dem
    Diktier-Motor (laeuft in EngineThread, siehe NovaFlowAppWithOverlay
    unten). Signale duerfen aus JEDEM Thread emittiert werden, Qt liefert
    sie dank QueuedConnection (siehe deren Verbindung in main()) garantiert
    im GUI-Thread aus - exakt dasselbe Muster wie bei UpdateCheckThread
    oben, eingefuehrt nach dem eingefrorenen Tray-Symbol vom 2026-07-25.
    """

    show_requested = pyqtSignal()
    hide_requested = pyqtSignal()
    level_changed = pyqtSignal(float)


class NovaFlowAppWithOverlay(NovaFlowApp):
    """NovaFlowApp-Variante mit angeschlossener Flowbar-Anzeige (JJ,
    2026-07-28). Reicht die in interface.py vorher leeren
    Kompatibilitaets-Stubs (show_overlay/hide_overlay/update_overlay_level)
    an die echte Flowbar weiter - ueber Signale statt direkter Aufrufe,
    weil diese Klasse im Hintergrund-Thread (EngineThread) laeuft, die
    Flowbar selbst aber ein echtes QWidget im GUI-Thread ist."""

    def __init__(self, overlay_bridge: "OverlayBridge"):
        self._overlay_bridge = overlay_bridge
        super().__init__()

    def show_overlay(self):
        self._overlay_bridge.show_requested.emit()

    def hide_overlay(self):
        self._overlay_bridge.hide_requested.emit()

    def update_overlay_level(self, rms: float):
        self._overlay_bridge.level_changed.emit(float(rms))


class EngineThread(QThread):
    """Laesst den Diktier-Motor (Hotkey-Listener + Verarbeitung) im Hintergrund laufen."""

    status_changed = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, overlay_bridge: "OverlayBridge | None" = None):
        super().__init__()
        self.app_instance = None
        self.overlay_bridge = overlay_bridge

    def run(self):
        try:
            self.app_instance = (
                NovaFlowAppWithOverlay(self.overlay_bridge)
                if self.overlay_bridge is not None
                else NovaFlowApp()
            )
            self.status_changed.emit("AKTIV")
            self.app_instance.run()
        except Exception as e:
            self.failed.emit(str(e))

    def stop(self):
        if self.app_instance:
            self.app_instance.stop()


class EngineController(QObject):
    """Kapselt den Diktier-Motor, damit er ueber das Einstellungsfenster
    gestartet und gestoppt werden kann, nicht nur beim App-Start.

    Ein QThread laesst sich in Qt nicht "pausieren", nur einmal komplett zu
    Ende laufen lassen. "Stop" beendet deshalb den kompletten Thread (die
    Interface-Schleife in interface.py bricht sauber ab), "Start" erzeugt
    bei Bedarf einen NEUEN EngineThread. Ein Fehlerfall (z.B. doppeltes
    Starten, waehrend der alte Thread noch beim Beenden ist) wird ueber
    is_busy()/status_text abgefangen, statt einfach zu versagen.

    MUSS ein QObject sein, das ist keine Kosmetik: alle Signale aus den
    Hintergrund-Threads landen in Methoden dieser Klasse. Qt kann eine
    Warteschlangen-Verbindung (QueuedConnection) nur dann garantiert in den
    richtigen Thread zustellen, wenn der Empfaenger ein QObject mit
    eindeutiger Thread-Zugehoerigkeit ist. Bei einer einfachen Python-Klasse
    oder einer verschachtelten Funktion gibt es keine solche Zugehoerigkeit,
    dann haengt das Verhalten an PyQt-Interna. Weil dieses Objekt im
    GUI-Thread erzeugt wird, gehoert es zum GUI-Thread und jede Zustellung
    landet nachweislich dort, wo Tray und Fenster angefasst werden duerfen.
    """

    def __init__(self, tray, overlay_bridge: "OverlayBridge | None" = None):
        super().__init__()
        self.tray = tray
        # Wird durchgereicht an EngineThread -> NovaFlowAppWithOverlay,
        # siehe dort. None ist gueltig (z.B. in Tests ohne echte
        # Qt-Oberflaeche), dann laeuft die einfache NovaFlowApp ohne
        # Flowbar-Anzeige.
        self.overlay_bridge = overlay_bridge
        # ACHTUNG: NICHT "self.thread" nennen. QObject hat bereits eine
        # Methode thread(), die wuerde dadurch ueberdeckt werden.
        self.engine_thread: EngineThread | None = None
        self.status_text = "Gestoppt"
        self.running = False
        self._on_status_callback = None
        self._on_failed_callback = None
        # Zuletzt gefundenes verfuegbares Update, gemeinsam von Tray und
        # Einstellungsfenster genutzt, damit beide denselben Stand kennen.
        self.pending_update = None
        # Halten die laufenden Hintergrund-Threads am Leben, bis sie fertig
        # sind, und merken sich, wohin das jeweilige Ergebnis gemeldet wird.
        self._check_callbacks = {}
        self._download_handlers = {}

    def set_ui_callbacks(self, on_status, on_failed):
        """Erlaubt novaflow.pyw, zusaetzlich auf Status-/Fehleraenderungen zu
        reagieren (Tray-Tooltip etc.), ohne dass die Kontrolllogik hier
        doppelt gepflegt werden muss."""
        self._on_status_callback = on_status
        self._on_failed_callback = on_failed

    def is_running(self) -> bool:
        return self.engine_thread is not None and self.engine_thread.isRunning()

    def start(self) -> bool:
        if self.is_running():
            return False
        self.engine_thread = EngineThread(overlay_bridge=self.overlay_bridge)
        self.engine_thread.status_changed.connect(self._on_status, QUEUED)
        self.engine_thread.failed.connect(self._on_failed, QUEUED)
        self.status_text = "Startet..."
        self.engine_thread.start()
        return True

    def stop(self) -> bool:
        if not self.is_running():
            return False
        self.status_text = "Wird beendet..."
        self.engine_thread.stop()
        return True

    def restart_hotkey_listener(self) -> bool:
        """Fuer den Notfallknopf: baut nur den Tastatur-Listener neu auf,
        nicht die ganze Anwendung samt Spracherkennungsmodell."""
        if not self.is_running() or self.engine_thread.app_instance is None:
            return False
        self.engine_thread.app_instance.restart_listener()
        return True

    def _on_status(self, status: str):
        self.status_text = status
        self.running = True
        if self._on_status_callback:
            self._on_status_callback(status)

    def _on_failed(self, message: str):
        self.status_text = f"Fehler: {message}"
        self.running = False
        if self._on_failed_callback:
            self._on_failed_callback(message)

    # ------------------------------------------------------------------
    # Update-Check/-Installation: gemeinsam von Tray-Menue und
    # Einstellungsfenster genutzt, damit es nur EINE Implementierung gibt,
    # die garantiert im Hintergrund laeuft. Die fruehere, separate Version
    # im Einstellungsfenster rief check_for_update() synchron im GUI-Thread
    # auf und fror das Fenster dabei ein ("Keine Rueckmeldung").
    # ------------------------------------------------------------------
    def check_for_update_async(self, manual: bool, callback) -> None:
        """Prueft im Hintergrund auf ein neues Release.

        callback(info: dict, manual: bool) wird im GUI-Thread aufgerufen,
        sobald das Ergebnis da ist. Mehrere gleichzeitig laufende Pruefungen
        (z.B. automatisch + manuell kurz hintereinander) sind
        unproblematisch, jede haelt sich selbst am Leben, bis sie fertig ist.

        Das Signal geht bewusst an eine gebundene Methode DIESES QObjects
        (_handle_check_result) und nicht an eine verschachtelte Funktion,
        siehe Klassenkommentar oben. Der eigentliche Rueckruf wird dort
        aufgerufen, dann laeuft er garantiert schon im GUI-Thread.
        """
        checker = UpdateCheckThread(manual=manual, parent=self)
        self._check_callbacks[checker] = callback
        checker.finished_check.connect(self._handle_check_result, QUEUED)
        checker.finished.connect(checker.deleteLater, QUEUED)
        checker.start()

    def _handle_check_result(self, info: dict, manual: bool) -> None:
        """Laeuft im GUI-Thread (QueuedConnection an ein QObject des GUI-Threads)."""
        checker = self.sender()
        callback = self._check_callbacks.pop(checker, None)
        if callback is None and len(self._check_callbacks) == 1:
            # Sehr unwahrscheinlicher Notfall: sender() nicht ermittelbar,
            # aber es kann nur eine einzige Pruefung gemeint sein.
            _, callback = self._check_callbacks.popitem()

        if info.get("available"):
            self.pending_update = info

        if callback:
            callback(info, manual)

    def install_update(self, info: dict, on_progress=None, on_error=None) -> None:
        """Laedt die neue Version im Hintergrund und startet den Installer.

        Beendet NovaFlow danach komplett (der Installer ersetzt die
        laufenden Programmdateien), egal ob ueber Tray oder
        Einstellungsfenster ausgeloest.
        """
        download_url = info.get("download_url", "")
        if sys.platform == "win32" and download_url:
            if on_progress:
                on_progress("Update wird heruntergeladen...")
            downloader = UpdateDownloadThread(download_url, parent=self)
            self._download_handlers[downloader] = on_error
            downloader.finished_download.connect(self._handle_download_done, QUEUED)
            downloader.finished.connect(downloader.deleteLater, QUEUED)
            downloader.start()
        else:
            # macOS (unsigniert, siehe NOTES.md) oder kein passender Download
            # gefunden: kein stiller Auto-Ersatz, stattdessen die
            # Release-Seite im Browser oeffnen, der Nutzer erledigt den Rest.
            import webbrowser

            webbrowser.open(
                info.get("release_url", "https://github.com/kiwerkepro-org/novaflow/releases/latest")
            )

    def _handle_download_done(self, path: str, error: str) -> None:
        """Laeuft im GUI-Thread (QueuedConnection an ein QObject des GUI-Threads)."""
        downloader = self.sender()
        on_error = self._download_handlers.pop(downloader, None)
        if on_error is None and len(self._download_handlers) == 1:
            _, on_error = self._download_handlers.popitem()

        if error:
            logger.error(
                f"Update-Download fehlgeschlagen: {error}",
                f"Update download failed: {error}",
            )
            if on_error:
                on_error(error)
            return

        try:
            import subprocess
            # /VERYSILENT etc.: NUR fuer diesen automatischen Update-Weg.
            # Bei der ALLERERSTEN Installation laedt sich der Nutzer die
            # Setup.exe selbst von GitHub und startet sie von Hand, DAS
            # bleibt der ganz normale interaktive Assistent (JJ will dort
            # bewusst die Kontrolle: Desktop-Symbol, Autostart, Ollama
            # ja/nein). Nur wenn eine schon laufende NovaFlow-Installation
            # sich selbst aktualisiert, ist Nachfragen unnoetig, die
            # Optionen wurden ja beim ersten Mal schon einmal bewusst
            # gewaehlt. UsePreviousTasks ist in installer.iss nicht
            # abgeschaltet (Standard: an), Inno Setup uebernimmt die
            # vorherige Auswahl (Desktop-Symbol, Autostart, Ollama)
            # automatisch, auch im stillen Modus, es geht dabei nichts
            # verloren. Dieselben Schalter laufen schon beim
            # Ollama-Unterinstaller in installer.iss.
            subprocess.Popen([path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"])
        except Exception as e:
            logger.error(
                f"Installer konnte nicht gestartet werden: {e}",
                f"Could not launch installer: {e}",
            )
            if on_error:
                on_error(str(e))
            return

        self.quit_app()

    def quit_app(self) -> None:
        """Beendet den Diktier-Motor sauber und danach die ganze Anwendung."""
        self.stop()
        app = QApplication.instance()
        if app:
            app.quit()


def _install_windows_taskbar_watchdog(app: QApplication, tray: QSystemTrayIcon):
    """Repariert das Tray-Symbol, falls es zu frueh registriert wurde.

    Bug (JJ, 2026-07-27): startet NovaFlow automatisch beim Windows-Login
    (siehe WindowsAutostart in src/platforms/windows.py), reagiert das
    Tray-Symbol danach weder auf Links- noch auf Rechtsklick - erst ein
    manuelles Beenden und Neustarten hilft. Bei einem normalen, manuellen
    Start tritt der Fehler nie auf.

    Ursache: der Windows-Infobereich (Teil von explorer.exe) ist beim Login
    nicht zwingend schon fertig aufgebaut, wenn der Autostart-Eintrag im
    Startup-Ordner bereits laeuft. Ruft QSystemTrayIcon.show() in diesem
    Fenster Shell_NotifyIcon(NIM_ADD) auf, kann der Aufruf erfolgreich
    zurueckkommen, ohne dass der Infobereich das Symbol wirklich mit dieser
    Anwendung verknuepft - es wird zwar (irgendwann) angezeigt, Klicks
    kommen aber nie mehr im Prozess an.

    Microsoft dokumentiert fuer genau diesen Fall die registrierte
    "TaskbarCreated"-Broadcast-Nachricht: sie wird an alle Top-Level-Fenster
    verschickt, sobald der Infobereich (neu) bereitsteht, sei es beim
    verzoegerten Hochfahren nach dem Login oder nach einem Explorer-Absturz.
    Darauf reagiert dieser Filter mit hide()+show(), das erzwingt intern ein
    neues Shell_NotifyIcon(NIM_ADD) und macht das Symbol wieder klickbar.

    Nur unter Windows relevant, macOS/Linux haben dieses Problem nicht.
    """
    if sys.platform != "win32":
        return None

    import ctypes
    import ctypes.wintypes
    from PyQt6.QtCore import QAbstractNativeEventFilter

    taskbar_created_id = ctypes.windll.user32.RegisterWindowMessageW("TaskbarCreated")

    class TaskbarRestartFilter(QAbstractNativeEventFilter):
        def nativeEventFilter(self, eventType, message):
            if eventType == b"windows_generic_MSG":
                msg = ctypes.wintypes.MSG.from_address(int(message))
                if msg.message == taskbar_created_id:
                    logger.info(
                        "Windows-Infobereich wurde (neu) bereitgestellt - "
                        "Tray-Symbol wird neu registriert...",
                        "Windows notification area became ready - "
                        "re-registering tray icon...",
                    )
                    tray.hide()
                    tray.show()
            return False, 0

    event_filter = TaskbarRestartFilter()
    app.installNativeEventFilter(event_filter)
    # Referenz am Leben halten: installNativeEventFilter haelt selbst keine
    # Python-Referenz, ohne dieses Attribut wuerde der Garbage Collector das
    # Objekt einsammeln und Qt liefe danach ins Leere.
    app._novaflow_taskbar_filter = event_filter
    return event_filter


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # laeuft im Tray weiter, auch wenn kein Fenster offen ist

    # Einzelinstanz-Schutz: verhindert doppelten Start und damit doppelt eingefuegten Text.
    guard = QSharedMemory(SINGLE_INSTANCE_KEY)
    if not guard.create(1):
        print(
            "[NovaFlow] Läuft schon: Es ist bereits eine NovaFlow-Instanz aktiv "
            "(siehe Tray-Symbol). Dieser zweite Start wird sofort beendet, "
            "das ist beabsichtigt und kein Fehler."
        )
        sys.exit(0)
    app._novaflow_single_instance = guard  # Referenz am Leben halten

    icon_path = project_root / "assets" / "icons" / "app" / "novaflow.ico"
    if icon_path.exists():
        tray_icon = QIcon(str(icon_path))
    else:
        tray_icon = app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)

    tray = QSystemTrayIcon(tray_icon)
    tray.setToolTip("NovaFlow – wird geladen...")

    menu = QMenu()
    update_action = QAction("Update verfügbar...")
    update_action.setVisible(False)  # erscheint erst, wenn wirklich eine neuere Version gefunden wurde
    menu.addAction(update_action)
    update_separator = menu.addSeparator()
    update_separator.setVisible(False)
    settings_action = QAction("Einstellungen")
    menu.addAction(settings_action)
    check_update_action = QAction("Nach Updates suchen")
    menu.addAction(check_update_action)
    restart_hotkey_action = QAction("Hotkey neu starten")
    menu.addAction(restart_hotkey_action)
    # Schnellumschaltung fuer den Rohtext-Modus (JJ, 2026-07-27): ueberspringt
    # die KI-Veredelung komplett, siehe NovaFlowProcessor.refine_text in
    # flow.py. Bewusst hier im Tray-Menue statt nur in den Einstellungen,
    # damit der Wechsel ohne Umweg ueber das Einstellungsfenster klappt.
    # setChecked() darf hier noch KEIN toggled-Signal auslösen (das würde
    # die .env unnötig mit dem eh schon aktuellen Wert erneut beschreiben),
    # deshalb wird die Verbindung erst NACH dem initialen setChecked() unten
    # hergestellt.
    raw_text_action = QAction("Rohtext-Modus (keine KI-Veredelung)")
    raw_text_action.setCheckable(True)
    raw_text_action.setChecked(config.get_bool("RAW_TEXT_MODE", False))
    menu.addAction(raw_text_action)
    menu.addSeparator()
    quit_action = QAction("Beenden")
    menu.addAction(quit_action)
    tray.setContextMenu(menu)
    tray.show()
    _install_windows_taskbar_watchdog(app, tray)

    # Flowbar (JJ, 2026-07-28): die Anzeige selbst lebt im GUI-Thread, die
    # Bridge stellt sicher, dass show_overlay/hide_overlay/update_overlay_level
    # aus dem Diktier-Motor (EngineThread) sie ueber QueuedConnection sicher
    # erreichen, siehe OverlayBridge/NovaFlowAppWithOverlay oben.
    flowbar = FlowbarOverlay()
    overlay_bridge = OverlayBridge()
    overlay_bridge.show_requested.connect(flowbar.show_and_reset, QUEUED)
    overlay_bridge.hide_requested.connect(flowbar.hide, QUEUED)
    overlay_bridge.level_changed.connect(flowbar.set_level, QUEUED)
    # Referenzen am Leben halten (siehe gleiches Muster bei
    # _novaflow_taskbar_filter/_novaflow_single_instance weiter unten).
    app._novaflow_flowbar = flowbar
    app._novaflow_overlay_bridge = overlay_bridge

    engine = EngineController(tray, overlay_bridge=overlay_bridge)
    # Referenz auf die Tray-Checkbox, damit das Einstellungsfenster (siehe
    # gui_settings_modal.py, save_settings()) sie nach dem Speichern direkt
    # mit umschalten kann, statt dass Tray und Einstellungen bis zum
    # naechsten Neustart auseinanderlaufen.
    engine.raw_text_action = raw_text_action

    def on_status(status: str):
        tray.setToolTip(f"NovaFlow – {status}")

    def on_failed(message: str):
        tray.setToolTip("NovaFlow – Fehler beim Start")
        tray.showMessage(
            "NovaFlow",
            f"Fehler beim Start: {message}",
            QSystemTrayIcon.MessageIcon.Critical,
        )
        logger.error(f"Engine-Fehler: {message}", f"Engine error: {message}")

    engine.set_ui_callbacks(on_status, on_failed)

    settings_dialog = {"instance": None}

    def open_settings():
        if settings_dialog["instance"] is None:
            # engine_api gibt dem Einstellungsfenster kontrollierten Zugriff
            # auf Start/Stop/Status, ohne dass es EngineThread/EngineController
            # selbst kennen muss (siehe Uebersicht-Seite in gui_settings_modal.py).
            settings_dialog["instance"] = NovaFlowSettingsModal(engine_api=engine)
            settings_dialog["instance"].finished.connect(
                lambda _: settings_dialog.update(instance=None)
            )
        settings_dialog["instance"].show()
        settings_dialog["instance"].raise_()
        settings_dialog["instance"].activateWindow()

    settings_action.triggered.connect(open_settings)

    def on_tray_activated(reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            open_settings()

    tray.activated.connect(on_tray_activated)

    def on_restart_hotkey():
        """Notfallknopf: baut nur den Tastatur-Listener neu auf.

        Windows kann einen Low-Level-Tastatur-Hook kommentarlos abhaengen
        (siehe ausfuehrlichen Kommentar in src/interface.py). Sollte das
        trotz aller Gegenmassnahmen doch einmal passieren, muss deswegen
        nicht die ganze Anwendung samt Spracherkennungsmodell neu starten.
        """
        if not engine.is_running():
            tray.showMessage(
                "NovaFlow",
                "NovaFlow läuft gerade nicht.",
                QSystemTrayIcon.MessageIcon.Information,
            )
            return
        try:
            engine.restart_hotkey_listener()
            tray.showMessage(
                "NovaFlow",
                "Hotkey wurde neu gestartet und ist wieder bereit.",
                QSystemTrayIcon.MessageIcon.Information,
            )
        except Exception as e:
            logger.error(
                f"Hotkey-Neustart fehlgeschlagen: {e}",
                f"Hotkey restart failed: {e}",
            )
            tray.showMessage(
                "NovaFlow",
                "Hotkey-Neustart fehlgeschlagen, bitte NovaFlow neu starten.",
                QSystemTrayIcon.MessageIcon.Warning,
            )

    restart_hotkey_action.triggered.connect(on_restart_hotkey)

    def on_raw_text_toggled(checked: bool):
        """Speichert den Rohtext-Modus dauerhaft (.env) und wirkt sofort,
        auch mitten in einer laufenden Sitzung: config ist ein Singleton
        (utils/config.py), NovaFlowProcessor.refine_text liest RAW_TEXT_MODE
        bei jedem einzelnen Diktat frisch aus, kein Neustart noetig."""
        secure_config.set("RAW_TEXT_MODE", "true" if checked else "false")
        if checked:
            tray.showMessage(
                "NovaFlow",
                "Rohtext-Modus aktiv: Diktate werden ohne KI-Veredelung eingefügt.",
                QSystemTrayIcon.MessageIcon.Information,
            )
        else:
            tray.showMessage(
                "NovaFlow",
                "Rohtext-Modus aus: KI-Veredelung ist wieder aktiv.",
                QSystemTrayIcon.MessageIcon.Information,
            )

    raw_text_action.toggled.connect(on_raw_text_toggled)

    def on_quit():
        engine.stop()
        app.quit()

    quit_action.triggered.connect(on_quit)

    # --- Update-Check -----------------------------------------------------
    # Fragt periodisch die GitHub-Releases-API ab (siehe utils/update_checker.py).
    # Ein Fehlschlag (kein Internet etc.) wird bewusst still ignoriert, das
    # darf niemals ein Fehler-Popup oder einen Absturz ausloesen.
    # Pruefung UND Download laufen beide ueber EngineController (siehe dort),
    # damit Tray und Einstellungsfenster dieselbe, threadsichere
    # Implementierung teilen, statt sie zweimal zu pflegen.

    def apply_update():
        if not engine.pending_update:
            return

        def _on_error(error):
            tray.showMessage(
                "NovaFlow",
                "Update-Download fehlgeschlagen. Bitte manuell von GitHub laden.",
                QSystemTrayIcon.MessageIcon.Warning,
            )

        def _on_progress(message):
            tray.showMessage("NovaFlow", message, QSystemTrayIcon.MessageIcon.Information)

        engine.install_update(engine.pending_update, on_progress=_on_progress, on_error=_on_error)

    update_action.triggered.connect(lambda checked=False: apply_update())

    def on_update_check_result(info: dict, manual: bool):
        check_update_action.setEnabled(True)
        check_update_action.setText("Nach Updates suchen")

        if info.get("available"):
            latest = info.get("latest_version", "?")
            update_action.setText(f"Update verfügbar (v{latest})...")
            update_action.setVisible(True)
            update_separator.setVisible(True)
            tray.showMessage(
                "NovaFlow Update verfügbar",
                f"Version {latest} steht bereit. Klick im Tray-Menü auf "
                f"\"Update verfügbar\", um zu aktualisieren.",
                QSystemTrayIcon.MessageIcon.Information,
            )
            return

        # Ab hier gibt es nichts Neues. Die automatische Pruefung schweigt
        # dazu bewusst, nur auf ausdruecklichen Wunsch gibt es eine Rueckmeldung.
        if not manual:
            return

        error = info.get("error")
        if error:
            tray.showMessage(
                "NovaFlow",
                "Update-Prüfung fehlgeschlagen. Besteht eine Internetverbindung?",
                QSystemTrayIcon.MessageIcon.Warning,
            )
            logger.warning(
                f"Manuelle Update-Prüfung fehlgeschlagen: {error}",
                f"Manual update check failed: {error}",
            )
            return

        current = info.get("current_version", "?")
        tray.showMessage(
            "NovaFlow",
            f"NovaFlow ist aktuell (Version {current}).",
            QSystemTrayIcon.MessageIcon.Information,
        )

    def run_update_check(manual: bool = False):
        engine.check_for_update_async(manual, on_update_check_result)

    def on_check_update_clicked():
        # Knopf sperren, solange geprüft wird. Verhindert, dass mehrfaches
        # Klicken unnötig viele Anfragen an GitHub schickt (unangemeldet
        # sind dort 60 Anfragen pro Stunde erlaubt).
        check_update_action.setEnabled(False)
        check_update_action.setText("Suche nach Updates...")
        run_update_check(manual=True)

    check_update_action.triggered.connect(on_check_update_clicked)

    update_timer = QTimer()
    update_timer.timeout.connect(lambda: run_update_check(manual=False))
    update_timer.start(UPDATE_CHECK_INTERVAL_MS)
    # Erster Check kurz nach dem Start, nicht sofort, damit er nicht mit dem
    # Hochfahren des Diktier-Motors um Ressourcen konkurriert.
    QTimer.singleShot(15000, lambda: run_update_check(manual=False))

    engine.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

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

# KRITISCH: ctranslate2 VOR PyQt6 importieren (verhindert Access Violation unter Windows,
# siehe gleiche Reihenfolge im bisherigen NovaFlow)
import ctranslate2  # noqa: E402,F401
import faster_whisper  # noqa: E402,F401

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QStyle  # noqa: E402
from PyQt6.QtCore import QThread, pyqtSignal, QSharedMemory  # noqa: E402
from PyQt6.QtGui import QIcon, QAction  # noqa: E402

from utils.logger import logger  # noqa: E402
from main import NovaFlowApp  # noqa: E402
from gui_settings_modal import NovaFlowSettingsModal  # noqa: E402

SINGLE_INSTANCE_KEY = "NovaFlow_SingleInstance_KIWERKE_NEXT"


class EngineThread(QThread):
    """Laesst den Diktier-Motor (Hotkey-Listener + Verarbeitung) im Hintergrund laufen."""

    status_changed = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.app_instance = None

    def run(self):
        try:
            self.app_instance = NovaFlowApp()
            self.status_changed.emit("AKTIV")
            self.app_instance.run()
        except Exception as e:
            self.failed.emit(str(e))

    def stop(self):
        if self.app_instance:
            self.app_instance.stop()


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
    settings_action = QAction("Einstellungen")
    menu.addAction(settings_action)
    menu.addSeparator()
    quit_action = QAction("Beenden")
    menu.addAction(quit_action)
    tray.setContextMenu(menu)
    tray.show()

    settings_dialog = {"instance": None}

    def open_settings():
        if settings_dialog["instance"] is None:
            settings_dialog["instance"] = NovaFlowSettingsModal()
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

    engine = EngineThread()

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

    engine.status_changed.connect(on_status)
    engine.failed.connect(on_failed)

    def on_quit():
        engine.stop()
        app.quit()

    quit_action.triggered.connect(on_quit)

    engine.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

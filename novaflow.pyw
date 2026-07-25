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

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QStyle  # noqa: E402
from PyQt6.QtCore import QThread, pyqtSignal, QSharedMemory, QTimer  # noqa: E402
from PyQt6.QtGui import QIcon, QAction  # noqa: E402

from utils.logger import logger  # noqa: E402
from utils.update_checker import check_for_update  # noqa: E402
from main import NovaFlowApp  # noqa: E402
from gui_settings_modal import NovaFlowSettingsModal  # noqa: E402

SINGLE_INSTANCE_KEY = "NovaFlow_SingleInstance_KIWERKE_NEXT"

# Alle 6 Stunden nach einer neueren Version schauen. Kein aggressiveres
# Intervall noetig, ein neues Release kommt nicht minuetlich.
UPDATE_CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000


class UpdateCheckThread(QThread):
    """Fragt im Hintergrund die GitHub-Releases-API ab, damit die
    Netzwerk-Anfrage die Tray-Oberflaeche nicht blockiert."""

    finished_check = pyqtSignal(dict)

    def run(self):
        try:
            result = check_for_update()
        except Exception as e:
            result = {"available": False, "error": str(e)}
        self.finished_check.emit(result)


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
    update_action = QAction("Update verfügbar...")
    update_action.setVisible(False)  # erscheint erst, wenn wirklich eine neuere Version gefunden wurde
    menu.addAction(update_action)
    update_separator = menu.addSeparator()
    update_separator.setVisible(False)
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

    # --- Update-Check -----------------------------------------------------
    # Fragt periodisch die GitHub-Releases-API ab (siehe utils/update_checker.py).
    # Ein Fehlschlag (kein Internet etc.) wird bewusst still ignoriert, das
    # darf niemals ein Fehler-Popup oder einen Absturz ausloesen.
    pending_update = {"info": None}

    def apply_update():
        info = pending_update["info"]
        if not info:
            return
        download_url = info.get("download_url", "")
        if sys.platform == "win32" and download_url:
            # Setup-Exe in einen temporaeren Ordner laden und starten. Der
            # Installer selbst killt die laufende NovaFlow.exe bereits in
            # InitializeSetup (siehe installer.iss) und installiert sauber
            # in dasselbe Verzeichnis (localappdata, keine Adminrechte
            # noetig), daher reicht "herunterladen, starten, uns selbst
            # beenden" hier vollstaendig aus.
            try:
                import tempfile
                import subprocess
                import requests as _requests

                tray.showMessage(
                    "NovaFlow",
                    "Update wird heruntergeladen...",
                    QSystemTrayIcon.MessageIcon.Information,
                )
                tmp_dir = Path(tempfile.gettempdir())
                installer_path = tmp_dir / "NovaFlow-Setup.exe"
                with _requests.get(download_url, stream=True, timeout=120) as resp:
                    resp.raise_for_status()
                    with open(installer_path, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=1024 * 256):
                            f.write(chunk)
                subprocess.Popen([str(installer_path)])
                on_quit()
            except Exception as e:
                logger.error(
                    f"Update-Download fehlgeschlagen: {e}", f"Update download failed: {e}"
                )
                tray.showMessage(
                    "NovaFlow",
                    "Update-Download fehlgeschlagen. Bitte manuell von GitHub laden.",
                    QSystemTrayIcon.MessageIcon.Warning,
                )
        else:
            # macOS (unsigniert, siehe NOTES.md) oder kein passender Download
            # gefunden: kein stiller Auto-Ersatz, stattdessen einfach die
            # Release-Seite im Browser oeffnen, der Nutzer erledigt den Rest.
            import webbrowser

            webbrowser.open(info.get("release_url", "https://github.com/kiwerkepro-org/novaflow/releases/latest"))

    update_action.triggered.connect(apply_update)

    def on_update_check_result(info: dict):
        if info.get("available"):
            pending_update["info"] = info
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

    def run_update_check():
        checker = UpdateCheckThread(app)
        checker.finished_check.connect(on_update_check_result)
        checker.finished.connect(checker.deleteLater)
        app._novaflow_update_checker = checker  # Referenz am Leben halten, bis fertig
        checker.start()

    update_timer = QTimer()
    update_timer.timeout.connect(run_update_check)
    update_timer.start(UPDATE_CHECK_INTERVAL_MS)
    # Erster Check kurz nach dem Start, nicht sofort, damit er nicht mit dem
    # Hochfahren des Diktier-Motors um Ressourcen konkurriert.
    QTimer.singleShot(15000, run_update_check)

    engine.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

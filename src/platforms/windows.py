"""
Windows-Implementierung der Plattform-Schnittstelle.

Die Zwischenablage- und Audio-Logik ist inhaltlich identisch mit dem, was
im bisherigen NovaFlow (C:\\KIW-SCHMIEDE\\NOVA-FLOW) in flow.py und
interface.py stand, nur jetzt sauber hinter der gemeinsamen Schnittstelle.

Zum Autostart: bewusst KEIN winreg-Run-Key. Im alten NovaFlow hat sich
gezeigt, dass dieser Weg auf manchen Windows-Installationen dauerhaft
wirkungslos ist (siehe CLAUDE.md dort). Zuverlaessig war stattdessen eine
kleine .vbs-Datei im Windows-Autostart-Ordner, genau das macht diese Klasse.
"""
import os
import sys
import time
from pathlib import Path
from typing import Any, Tuple

from pynput.keyboard import Key

from platforms.base import Platform, ClipboardBackend, AudioMuteBackend, AutostartBackend
from utils.logger import logger
from utils.paths import get_project_root

STARTUP_VBS_NAME = "NovaFlow-Autostart.vbs"


class WindowsClipboard(ClipboardBackend):
    def backup(self) -> Tuple[str, Any]:
        try:
            import win32clipboard as wc
            import win32con
            wanted = [win32con.CF_UNICODETEXT, win32con.CF_DIB]
            data = {}
            for _ in range(15):
                try:
                    wc.OpenClipboard()
                    try:
                        for fmt in wanted:
                            if wc.IsClipboardFormatAvailable(fmt):
                                try:
                                    data[fmt] = wc.GetClipboardData(fmt)
                                except Exception:
                                    pass
                    finally:
                        wc.CloseClipboard()
                    return ("win32", data)
                except Exception:
                    time.sleep(0.04)
            return ("win32", data)
        except Exception:
            try:
                import pyperclip
                return ("text", pyperclip.paste())
            except Exception:
                return ("text", "")

    def restore(self, backup: Tuple[str, Any]) -> None:
        art, data = backup
        if art == "win32":
            if not data:
                return
            try:
                import win32clipboard as wc
                for _ in range(15):
                    try:
                        wc.OpenClipboard()
                        try:
                            wc.EmptyClipboard()
                            for fmt, val in data.items():
                                try:
                                    wc.SetClipboardData(fmt, val)
                                except Exception:
                                    pass
                        finally:
                            wc.CloseClipboard()
                        return
                    except Exception:
                        time.sleep(0.04)
            except Exception:
                pass
        else:
            self._restore_text(data)

    def _restore_text(self, text: str) -> None:
        try:
            import pyperclip
            for _ in range(20):
                try:
                    pyperclip.copy(text)
                    time.sleep(0.03)
                    if pyperclip.paste() == text:
                        return
                except Exception:
                    time.sleep(0.04)
        except Exception:
            pass

    def write_text(self, text: str) -> bool:
        try:
            import pyperclip
            for _ in range(25):
                try:
                    pyperclip.copy(text)
                    time.sleep(0.03)
                    if pyperclip.paste() == text:
                        return True
                except Exception:
                    time.sleep(0.04)
        except Exception:
            pass
        return False

    def read_text(self) -> str:
        try:
            import pyperclip
            return pyperclip.paste()
        except Exception:
            return ""


class WindowsAudioMute(AudioMuteBackend):
    """Stummschaltung ausschliesslich ueber pycaw (Windows CoreAudio API).

    Frueher gab es hier zusaetzlich einen nircmd.exe-Weg als ersten
    Versuch. Der wurde entfernt: nircmd.exe wird von Windows Defender und
    diversen Antivirus-Programmen gerne faelschlich als potenziell
    unerwuenschtes Tool eingestuft und nach der Installation automatisch
    geloescht bzw. in Quarantaene verschoben (bestaetigt beim ersten Test
    des gepackten Installers: nircmd.exe war nach der Installation
    verschwunden, obwohl es beim Bauen korrekt mitgeliefert wurde). pycaw
    ist eine normale Python-Bibliothek ohne dieses Problem.

    pycaw hat ausserdem im Laufe der Zeit seine API geaendert:
    - Aeltere Versionen: AudioUtilities.GetSpeakers() liefert ein rohes
      COM-Objekt, an dem man per .Activate(...) die Lautstaerke-Schnittstelle
      holen muss.
    - Neuere Versionen: AudioUtilities.GetSpeakers() liefert ein
      AudioDevice-Wrapper-Objekt mit einer fertigen .EndpointVolume-
      Eigenschaft, .Activate(...) existiert darauf nicht mehr.
    _get_volume_interface() probiert beide Varianten, damit es unabhaengig
    von der zur Build-Zeit installierten pycaw-Version funktioniert.
    """

    def __init__(self):
        self._original_volume = None
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # noqa: F401
            self._pycaw_available = True
        except Exception:
            self._pycaw_available = False

        if self._pycaw_available:
            logger.debug("pycaw Audio-Muting verfügbar", "pycaw audio muting available")
        else:
            logger.warning(
                "Kein Audio-Muting verfügbar (pycaw nicht installiert)",
                "No audio muting available (pycaw not installed)"
            )

    def _get_volume_interface(self):
        from ctypes import cast, POINTER
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()

        # Neuere pycaw-Version: fertige .EndpointVolume-Eigenschaft.
        endpoint_volume = getattr(devices, "EndpointVolume", None)
        if endpoint_volume is not None:
            return endpoint_volume

        # Aeltere pycaw-Version: manuell per .Activate(...) aktivieren.
        try:
            from comtypes import CLSCTX_ALL
        except Exception:
            CLSCTX_ALL = 1  # CLSCTX_INPROC_SERVER, funktioniert als Fallback
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))

    def mute(self) -> None:
        if not self._pycaw_available:
            return
        try:
            volume = self._get_volume_interface()
            self._original_volume = volume.GetMasterVolumeLevelScalar()
            volume.SetMasterVolumeLevelScalar(0, None)
            logger.debug("Lautsprecher stummgeschaltet (pycaw)", "Speakers muted (pycaw)")
        except Exception as e:
            logger.debug(f"pycaw Mute-Fehler: {str(e)}", f"pycaw mute error: {str(e)}")

    def unmute(self) -> None:
        if not self._pycaw_available or self._original_volume is None:
            return
        try:
            volume = self._get_volume_interface()
            volume.SetMasterVolumeLevelScalar(self._original_volume, None)
            logger.debug("Lautsprecher reaktiviert (pycaw)", "Speakers unmuted (pycaw)")
        except Exception as e:
            logger.debug(f"pycaw Unmute-Fehler: {str(e)}", f"pycaw unmute error: {str(e)}")


class WindowsAutostart(AutostartBackend):
    def _startup_dir(self) -> Path:
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"

    def _vbs_path(self) -> Path:
        return self._startup_dir() / STARTUP_VBS_NAME

    def is_enabled(self) -> bool:
        return self._vbs_path().exists()

    def enable(self) -> bool:
        try:
            target = sys.executable
            arg = ""
            if not getattr(sys, "frozen", False):
                # Normaler Python-Betrieb: pythonw.exe + novaflow.pyw
                entry = get_project_root() / "novaflow.pyw"
                arg = f'"{entry}"'
            vbs_content = (
                'Set WshShell = CreateObject("WScript.Shell")\n'
                f'WshShell.CurrentDirectory = "{get_project_root()}"\n'
                f'WshShell.Run """{target}"" {arg}", 0, False\n'
            )
            self._startup_dir().mkdir(parents=True, exist_ok=True)
            self._vbs_path().write_text(vbs_content, encoding="utf-8")
            return True
        except Exception as e:
            logger.warning(f"Autostart konnte nicht eingerichtet werden: {e}")
            return False

    def disable(self) -> bool:
        try:
            if self._vbs_path().exists():
                self._vbs_path().unlink()
            return True
        except Exception as e:
            logger.warning(f"Autostart konnte nicht entfernt werden: {e}")
            return False


class WindowsPlatform(Platform):
    name = "windows"

    def _build_clipboard(self) -> ClipboardBackend:
        return WindowsClipboard()

    def _build_audio_mute(self) -> AudioMuteBackend:
        return WindowsAudioMute()

    def _build_autostart(self) -> AutostartBackend:
        return WindowsAutostart()

    def default_hotkey(self) -> str:
        return "ctrl_win"

    def paste_key(self):
        return Key.ctrl

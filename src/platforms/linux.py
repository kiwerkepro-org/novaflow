"""
Linux-Implementierung der Plattform-Schnittstelle – BEWUSST NUR EIN PLATZHALTER.

Linux ist kein einheitliches Ziel: Zwischenablage- und Autostart-Mechanismen
unterscheiden sich schon zwischen Desktop-Umgebungen, und beim globalen
Abhoeren einer gehaltenen Tastenkombination gibt es unter Wayland (im
Unterschied zu X11) aus Sicherheitsgruenden echte Einschraenkungen, viele
Programme koennen dort gar nicht mehr systemweit auf Tasten lauschen.

Diese Klasse ist deshalb bewusst zurueckhaltend:
- Zwischenablage: nur Text, ueber pyperclip (nutzt xclip/xsel unter X11).
  Bilder werden NICHT gesichert (anders als bei Windows/Mac).
- Stummschaltung: bewusst ein No-Op mit Log-Hinweis statt eines falschen
  Erfolgsgefuehls, da es keine einheitliche API gibt (PulseAudio, PipeWire,
  ALSA unterscheiden sich je nach Distribution).
- Autostart: ueber einen XDG-Autostart .desktop-Eintrag, das ist der
  Standard-Mechanismus und funktioniert distributionsuebergreifend.

Bevor hier ernsthaft mehr gemacht wird, muss zuerst geklaert werden, welche
Linux-Umgebung (X11 vs. Wayland, welche Desktop-Umgebung) ueberhaupt
unterstuetzt werden soll.
"""
import sys
import time
from pathlib import Path
from typing import Any, Tuple

from pynput.keyboard import Key

from platforms.base import Platform, ClipboardBackend, AudioMuteBackend, AutostartBackend
from utils.logger import logger
from utils.paths import get_project_root

AUTOSTART_DESKTOP_NAME = "novaflow.desktop"


class LinuxClipboard(ClipboardBackend):
    """Nur Text, ueber pyperclip. Bilder werden hier (noch) nicht unterstuetzt."""

    def backup(self) -> Tuple[str, Any]:
        try:
            import pyperclip
            return ("text", pyperclip.paste())
        except Exception:
            return ("text", "")

    def restore(self, backup: Tuple[str, Any]) -> None:
        _art, data = backup
        try:
            import pyperclip
            for _ in range(20):
                try:
                    pyperclip.copy(data)
                    time.sleep(0.03)
                    if pyperclip.paste() == data:
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


class LinuxAudioMute(AudioMuteBackend):
    """Absichtlich ein No-Op: keine verlaessliche, distributionsuebergreifende API."""

    _warned = False

    def mute(self) -> None:
        if not LinuxAudioMute._warned:
            logger.warning(
                "Audio-Stummschaltung unter Linux noch nicht umgesetzt (PulseAudio/PipeWire/ALSA "
                "unterscheiden sich je Distribution) - Aufnahme laeuft ohne Stummschaltung weiter",
                "Audio muting not yet implemented on Linux - recording continues without muting"
            )
            LinuxAudioMute._warned = True

    def unmute(self) -> None:
        pass


class LinuxAutostart(AutostartBackend):
    """XDG-Autostart .desktop-Eintrag, Standardmechanismus unter Linux."""

    def _autostart_dir(self) -> Path:
        return Path.home() / ".config" / "autostart"

    def _desktop_path(self) -> Path:
        return self._autostart_dir() / AUTOSTART_DESKTOP_NAME

    def is_enabled(self) -> bool:
        return self._desktop_path().exists()

    def enable(self) -> bool:
        try:
            if getattr(sys, "frozen", False):
                exec_line = sys.executable
            else:
                exec_line = f'{sys.executable} "{get_project_root() / "novaflow.pyw"}"'
            content = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=NovaFlow\n"
                f"Exec={exec_line}\n"
                "X-GNOME-Autostart-enabled=true\n"
            )
            self._autostart_dir().mkdir(parents=True, exist_ok=True)
            self._desktop_path().write_text(content, encoding="utf-8")
            return True
        except Exception as e:
            logger.warning(f"Autostart konnte nicht eingerichtet werden: {e}")
            return False

    def disable(self) -> bool:
        try:
            if self._desktop_path().exists():
                self._desktop_path().unlink()
            return True
        except Exception as e:
            logger.warning(f"Autostart konnte nicht entfernt werden: {e}")
            return False


class LinuxPlatform(Platform):
    name = "linux"

    def _build_clipboard(self) -> ClipboardBackend:
        return LinuxClipboard()

    def _build_audio_mute(self) -> AudioMuteBackend:
        return LinuxAudioMute()

    def _build_autostart(self) -> AutostartBackend:
        return LinuxAutostart()

    def default_hotkey(self) -> str:
        # Unter Wayland kann das globale Abhoeren einer gehaltenen Taste
        # aus Sicherheitsgruenden eingeschraenkt oder blockiert sein.
        return "ctrl_alt"

    def paste_key(self):
        return Key.ctrl

"""
macOS-Implementierung der Plattform-Schnittstelle.

Zwischenablage ueber AppKit/NSPasteboard (pyobjc), Stummschaltung ueber
osascript (kein zusaetzliches natives Paket noetig, funktioniert auf jeder
macOS-Version), Autostart ueber einen LaunchAgent statt eines Windows-Style
Registry-Eintrags.
"""
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Tuple

from pynput.keyboard import Key

from platforms.base import Platform, ClipboardBackend, AudioMuteBackend, AutostartBackend
from utils.logger import logger
from utils.paths import get_project_root

LAUNCH_AGENT_LABEL = "eu.kiw-schmiede.novaflow"


class MacClipboard(ClipboardBackend):
    """Nutzt AppKit/NSPasteboard fuer Text UND Bilder, faellt auf pyperclip zurueck."""

    def _pasteboard(self):
        from AppKit import NSPasteboard
        return NSPasteboard.generalPasteboard()

    def backup(self) -> Tuple[str, Any]:
        try:
            from AppKit import NSPasteboardTypeString, NSPasteboardTypeTIFF
            pb = self._pasteboard()
            data = {}
            text = pb.stringForType_(NSPasteboardTypeString)
            if text:
                data["text"] = str(text)
            image_data = pb.dataForType_(NSPasteboardTypeTIFF)
            if image_data:
                data["tiff"] = bytes(image_data)
            return ("mac", data)
        except Exception:
            try:
                import pyperclip
                return ("text", pyperclip.paste())
            except Exception:
                return ("text", "")

    def restore(self, backup: Tuple[str, Any]) -> None:
        art, data = backup
        if art == "mac":
            if not data:
                return
            try:
                from AppKit import NSPasteboardTypeString, NSPasteboardTypeTIFF
                from Foundation import NSData
                pb = self._pasteboard()
                pb.clearContents()
                if "text" in data:
                    pb.setString_forType_(data["text"], NSPasteboardTypeString)
                if "tiff" in data:
                    ns_data = NSData.dataWithBytes_length_(data["tiff"], len(data["tiff"]))
                    pb.setData_forType_(ns_data, NSPasteboardTypeTIFF)
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


class MacAudioMute(AudioMuteBackend):
    """Stummschaltung ueber osascript/System Events, ohne Extra-Abhaengigkeit."""

    def __init__(self):
        self._was_muted_before = None
        self._is_muted_by_us = False

    def mute(self) -> None:
        # Doppeltes Stummschalten wuerde den gemerkten Ausgangszustand
        # ueberschreiben (dann waere "vorher schon stumm" gemerkt und
        # unmute() wuerde nichts mehr tun). Gleiche Absicherung wie unter
        # Windows, siehe platforms/windows.py.
        if self._is_muted_by_us:
            logger.debug(
                "Bereits stummgeschaltet, Ausgangszustand bleibt erhalten.",
                "Already muted, keeping original state.",
            )
            return
        try:
            result = subprocess.run(
                ["osascript", "-e", "output muted of (get volume settings)"],
                capture_output=True, text=True, check=False
            )
            self._was_muted_before = (result.stdout.strip().lower() == "true")
            subprocess.run(["osascript", "-e", "set volume output muted true"], check=False, capture_output=True)
            self._is_muted_by_us = True
            logger.debug("Lautsprecher stummgeschaltet (osascript)", "Speakers muted (osascript)")
        except Exception as e:
            logger.debug(f"osascript Mute-Fehler: {str(e)}", f"osascript mute error: {str(e)}")

    def unmute(self) -> None:
        was_muted_before = self._was_muted_before
        # Zustand IMMER zuruecksetzen, sonst blockiert ein einmaliger Fehler
        # jedes weitere mute().
        self._is_muted_by_us = False
        self._was_muted_before = None

        if was_muted_before:
            # War vorher schon stumm -> Nutzerwunsch respektieren, nichts aendern
            return
        try:
            subprocess.run(["osascript", "-e", "set volume output muted false"], check=False, capture_output=True)
            logger.debug("Lautsprecher reaktiviert (osascript)", "Speakers unmuted (osascript)")
        except Exception as e:
            logger.debug(f"osascript Unmute-Fehler: {str(e)}", f"osascript unmute error: {str(e)}")


class MacAutostart(AutostartBackend):
    """Autostart ueber einen LaunchAgent in ~/Library/LaunchAgents."""

    def _plist_path(self) -> Path:
        return Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"

    def is_enabled(self) -> bool:
        return self._plist_path().exists()

    def enable(self) -> bool:
        try:
            if getattr(sys, "frozen", False):
                program_args = [sys.executable]
            else:
                program_args = [sys.executable, str(get_project_root() / "novaflow.pyw")]
            args_xml = "\n".join(f"        <string>{a}</string>" for a in program_args)
            plist = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                '<plist version="1.0">\n'
                '<dict>\n'
                f'    <key>Label</key>\n    <string>{LAUNCH_AGENT_LABEL}</string>\n'
                '    <key>ProgramArguments</key>\n    <array>\n'
                f'{args_xml}\n'
                '    </array>\n'
                '    <key>RunAtLoad</key>\n    <true/>\n'
                '</dict>\n'
                '</plist>\n'
            )
            self._plist_path().parent.mkdir(parents=True, exist_ok=True)
            self._plist_path().write_text(plist, encoding="utf-8")
            subprocess.run(["launchctl", "load", str(self._plist_path())], check=False, capture_output=True)
            return True
        except Exception as e:
            logger.warning(f"Autostart konnte nicht eingerichtet werden: {e}")
            return False

    def disable(self) -> bool:
        try:
            if self._plist_path().exists():
                subprocess.run(["launchctl", "unload", str(self._plist_path())], check=False, capture_output=True)
                self._plist_path().unlink()
            return True
        except Exception as e:
            logger.warning(f"Autostart konnte nicht entfernt werden: {e}")
            return False


class MacPlatform(Platform):
    name = "macos"

    def _build_clipboard(self) -> ClipboardBackend:
        return MacClipboard()

    def _build_audio_mute(self) -> AudioMuteBackend:
        return MacAudioMute()

    def _build_autostart(self) -> AutostartBackend:
        return MacAutostart()

    def default_hotkey(self) -> str:
        return "ctrl_cmd"

    def paste_key(self):
        return Key.cmd

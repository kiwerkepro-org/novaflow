"""
NovaFlow Plattform-Schnittstelle.

Buendelt alles, was sich zwischen Windows, Mac und Linux unterscheidet:
- Zwischenablage sichern/wiederherstellen (inkl. Bilder, soweit moeglich)
- Lautsprecher waehrend der Aufnahme stummschalten
- Autostart beim Systemstart einrichten
- Standard-Hotkey und Einfuege-Tastenkombination

Der Rest von NovaFlow (interface.py, flow.py, main.py) kennt NUR diese
Schnittstelle und ruft nirgends direkt win32clipboard, AppKit o.ae. auf.
Neue Plattformen (aktuell: Linux) werden hinzugefuegt, indem einfach eine
weitere Klasse hier implementiert wird, ohne den Rest von NovaFlow anzufassen.
"""
from abc import ABC, abstractmethod
from typing import Any, Tuple


class ClipboardBackend(ABC):
    """Sichern/Wiederherstellen der System-Zwischenablage."""

    @abstractmethod
    def backup(self) -> Tuple[str, Any]:
        """Sichert den aktuellen Inhalt. Rueckgabe: (art, daten)."""

    @abstractmethod
    def restore(self, backup: Tuple[str, Any]) -> None:
        """Stellt einen zuvor gesicherten Inhalt wieder her."""

    @abstractmethod
    def write_text(self, text: str) -> bool:
        """Schreibt Text in die Zwischenablage, prueft ob es angekommen ist."""

    @abstractmethod
    def read_text(self) -> str:
        """Liest den aktuellen Text-Inhalt der Zwischenablage."""


class AudioMuteBackend(ABC):
    """Lautsprecher waehrend der Aufnahme stumm schalten."""

    @abstractmethod
    def mute(self) -> None:
        ...

    @abstractmethod
    def unmute(self) -> None:
        ...


class AutostartBackend(ABC):
    """Autostart-Eintrag beim Systemstart verwalten."""

    @abstractmethod
    def is_enabled(self) -> bool:
        ...

    @abstractmethod
    def enable(self) -> bool:
        ...

    @abstractmethod
    def disable(self) -> bool:
        ...


class Platform(ABC):
    """Fasst alle Bausteine einer Betriebssystem-Implementierung zusammen."""

    name = "base"

    def __init__(self):
        self._clipboard = None
        self._audio_mute = None
        self._autostart = None

    @property
    def clipboard(self) -> ClipboardBackend:
        if self._clipboard is None:
            self._clipboard = self._build_clipboard()
        return self._clipboard

    @property
    def audio_mute(self) -> AudioMuteBackend:
        if self._audio_mute is None:
            self._audio_mute = self._build_audio_mute()
        return self._audio_mute

    @property
    def autostart(self) -> AutostartBackend:
        if self._autostart is None:
            self._autostart = self._build_autostart()
        return self._autostart

    @abstractmethod
    def _build_clipboard(self) -> ClipboardBackend:
        ...

    @abstractmethod
    def _build_audio_mute(self) -> AudioMuteBackend:
        ...

    @abstractmethod
    def _build_autostart(self) -> AutostartBackend:
        ...

    @abstractmethod
    def default_hotkey(self) -> str:
        """Plattformtypischer Standard-Hotkey (z.B. 'ctrl_win' / 'ctrl_cmd')."""

    @abstractmethod
    def paste_key(self):
        """Gibt den pynput-Modifier-Key fuer 'Einfuegen' zurueck (Ctrl bzw. Cmd)."""

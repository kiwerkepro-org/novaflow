"""
NovaFlow Interface – Audio Capture & Hotkey Management
Handhabt Mikrofon-Input und Hotkey-Erkennung.

Gegenueber dem bisherigen NovaFlow ist nur die Audio-Stummschaltung
geaendert: die laeuft jetzt ueber platforms.get_platform().audio_mute
statt direkt ueber nircmd/pycaw. Hotkey-Erkennung ueber pynput ist bereits
plattformunabhaengig, nur der STANDARD-Hotkey kommt jetzt von der
Plattform (ctrl_win unter Windows, ctrl_cmd unter Mac).
"""
import os
import tempfile
from pathlib import Path
from typing import Optional, Callable
import numpy as np
import sounddevice as sd
import soundfile as sf
from pynput import keyboard

from utils.logger import logger
from utils.config import config
from platforms import get_platform


class FlowInterface:
    """Verwaltet Audio-Aufnahme und Hotkey-Steuerung"""

    def __init__(self, hotkey_callback: Optional[Callable] = None):
        self.hotkey_callback = hotkey_callback
        self.is_recording = False
        self.audio_data = []
        self.sample_rate = config.get("SAMPLE_RATE", 16000)
        self.stream = None
        self.listener = None
        self.platform = get_platform()

        # Temporary file path
        self.temp_dir = Path(tempfile.gettempdir())
        self.temp_filepath = self.temp_dir / "novaflow_audio.wav"

        # Aktuell gedrückte Tasten (für Combo-Support)
        self._pressed = set()

        # Verhindert erneuten Hotkey-Trigger während Text-Injektion
        self._hotkey_blocked = False

        # Parse hotkey von Config (unterstützt Combos wie ctrl_win / ctrl_cmd)
        self.hotkey_keys = self._parse_hotkey()

        logger.info(
            f"Interface initialisiert - Hotkey: {self._active_hotkey_str()} ({self.platform.name})",
            f"Interface initialized - Hotkey: {self._active_hotkey_str()} ({self.platform.name})"
        )

    def _active_hotkey_str(self) -> str:
        configured = config.get("HOTKEY", "").strip()
        return configured if configured else self.platform.default_hotkey()

    def _mute_audio(self):
        """Stummschaltet die Lautsprecher (plattformabhaengig)"""
        try:
            self.platform.audio_mute.mute()
        except Exception as e:
            logger.debug(f"Audio-Mute-Fehler: {str(e)}", f"Audio mute error: {str(e)}")

    def _unmute_audio(self):
        """Reaktiviert die Lautsprecher (plattformabhaengig)"""
        try:
            self.platform.audio_mute.unmute()
        except Exception as e:
            logger.debug(f"Audio-Unmute-Fehler: {str(e)}", f"Audio unmute error: {str(e)}")

    def _normalize_key(self, key):
        """Normalisiert links/rechts Modifier-Varianten zu kanonischen Keys"""
        normalize = {
            keyboard.Key.ctrl_l: keyboard.Key.ctrl,
            keyboard.Key.ctrl_r: keyboard.Key.ctrl,
            keyboard.Key.alt_l: keyboard.Key.alt,
            keyboard.Key.alt_r: keyboard.Key.alt,
            keyboard.Key.shift_l: keyboard.Key.shift,
            keyboard.Key.shift_r: keyboard.Key.shift,
            keyboard.Key.cmd_l: keyboard.Key.cmd,
            keyboard.Key.cmd_r: keyboard.Key.cmd,
        }
        return normalize.get(key, key)

    def _parse_hotkey(self) -> frozenset:
        """Parst Hotkey-String zu frozenset von pynput Keys (unterstützt Combos)"""
        hotkey_str = self._active_hotkey_str().lower()

        key_map = {
            "alt_gr": keyboard.Key.alt_gr,
            "ctrl": keyboard.Key.ctrl,
            "alt": keyboard.Key.alt,
            "shift": keyboard.Key.shift,
            "win": keyboard.Key.cmd,
            "cmd": keyboard.Key.cmd,
        }

        if hotkey_str in key_map:
            return frozenset({key_map[hotkey_str]})

        parts = hotkey_str.replace("+", "_").split("_")
        keys = set()
        i = 0
        while i < len(parts):
            if i + 1 < len(parts):
                two = f"{parts[i]}_{parts[i+1]}"
                if two in key_map:
                    keys.add(key_map[two])
                    i += 2
                    continue
            if parts[i] in key_map:
                keys.add(key_map[parts[i]])
            i += 1

        return frozenset(keys) if keys else frozenset({keyboard.Key.alt_gr})

    def audio_callback(self, indata, frames, time, status):
        """Callback für Audio-Stream"""
        if status:
            logger.debug(f"Audio Status: {status}", f"Audio Status: {status}")

        if self.is_recording and indata is not None:
            self.audio_data.append(indata.copy())

    def start_recording(self):
        """Startet Audio-Aufnahme und stummschaltet Lautsprecher"""
        try:
            logger.info(
                "Aufnahme gestartet... (Taste loslassen zum Beenden)",
                "Recording started... (Release key to stop)"
            )

            self.audio_data = []
            self.is_recording = True

            self._mute_audio()

            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                callback=self.audio_callback,
                blocksize=4096
            )
            self.stream.start()

        except Exception as e:
            logger.error(f"Fehler beim Starten der Aufnahme: {str(e)}", f"Error starting recording: {str(e)}")
            self.is_recording = False

    def stop_recording(self) -> Optional[Path]:
        """Stoppt Aufnahme, reaktiviert Lautsprecher und speichert Datei"""
        try:
            logger.info("Aufnahme beendet. Speichere Datei...", "Recording stopped. Saving file...")

            self.is_recording = False

            self._unmute_audio()

            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None

            if self.audio_data:
                audio_np = np.concatenate(self.audio_data, axis=0)
                sf.write(str(self.temp_filepath), audio_np, self.sample_rate)

                logger.success(
                    f"Datei gespeichert: {self.temp_filepath.name}",
                    f"File saved: {self.temp_filepath.name}"
                )

                return self.temp_filepath
            else:
                logger.warning("Keine Audio-Daten aufgezeichnet", "No audio data recorded")
                return None

        except Exception as e:
            logger.error(f"Fehler beim Speichern: {str(e)}", f"Error saving file: {str(e)}")
            self._unmute_audio()
            return None

    def unblock_hotkey(self):
        """Gibt Hotkey nach Text-Injektion wieder frei"""
        self._hotkey_blocked = False
        self._pressed.clear()
        logger.debug("Hotkey freigegeben", "Hotkey unblocked")
        try:
            from utils.audio_feedback import audio_feedback
            audio_feedback.play_ready()
        except Exception:
            pass

    def hide_overlay(self):
        """Kompatibilitäts-Stub – überschreibbar durch Subklassen"""
        pass

    def on_press(self, key):
        """Callback für Tasten-Druck – alle Exceptions werden abgefangen"""
        try:
            if self._hotkey_blocked:
                return
            norm = self._normalize_key(key)
            self._pressed.add(norm)
            if self.hotkey_keys.issubset(self._pressed) and not self.is_recording:
                self.start_recording()
        except Exception:
            pass

    def on_release(self, key):
        """Callback für Tasten-Release – alle Exceptions werden abgefangen"""
        try:
            norm = self._normalize_key(key)
            if norm in self.hotkey_keys and self.is_recording:
                was_recording = self.is_recording
                self.is_recording = False
                self._pressed.discard(norm)
                if was_recording:
                    self._hotkey_blocked = True
                    audio_file = self.stop_recording()
                    if audio_file and self.hotkey_callback:
                        self.hotkey_callback(audio_file)
            else:
                self._pressed.discard(norm)
        except Exception:
            pass

    def run(self):
        """Startet den Hotkey-Listener (blocking) mit Auto-Restart bei Absturz"""
        import time
        logger.info(
            f"Nova Flow Interface läuft. Halte {self._active_hotkey_str()} gedrückt, um zu sprechen.",
            f"Nova Flow Interface running. Press and hold {self._active_hotkey_str()} to speak."
        )
        self._running = True
        while self._running:
            try:
                with keyboard.Listener(
                    on_press=self.on_press,
                    on_release=self.on_release
                ) as listener:
                    self.listener = listener
                    listener.join()

                if not self._running:
                    break

                logger.warning(
                    "Keyboard-Listener unerwartet beendet – Neustart in 1s...",
                    "Keyboard listener stopped unexpectedly – restarting in 1s..."
                )
                self.is_recording = False
                self._hotkey_blocked = False
                self._pressed.clear()
                time.sleep(1)

            except KeyboardInterrupt:
                logger.info("Interface beendet", "Interface stopped")
                self._running = False
                break
            except Exception as e:
                logger.error(
                    f"Interface Fehler: {str(e)} – Neustart in 2s...",
                    f"Interface error: {str(e)} – restarting in 2s..."
                )
                self.is_recording = False
                self._hotkey_blocked = False
                self._pressed.clear()
                time.sleep(2)

    def stop(self):
        """Stoppt den Listener und beendet den Restart-Loop"""
        self._running = False
        if self.listener:
            self.listener.stop()

    def cleanup(self):
        """Bereinigung"""
        if self.stream:
            self.stream.close()

        if self.temp_filepath.exists():
            try:
                os.remove(str(self.temp_filepath))
                logger.debug("Temp-Datei gelöscht", "Temp file deleted")
            except Exception as e:
                logger.debug(f"Fehler beim Löschen: {str(e)}", f"Error deleting: {str(e)}")

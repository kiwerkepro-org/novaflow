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
import queue
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional, Callable
import numpy as np
import sounddevice as sd
import soundfile as sf
from pynput import keyboard

from utils.logger import logger
from utils.config import config
from platforms import get_platform

# Notbremse: laenger als so viele Sekunden darf die Hotkey-Sperre nie
# bestehen bleiben. Selbst wenn irgendwo in der Verarbeitungskette ein
# unvorhergesehener Pfad das Freigeben vergisst, macht sich NovaFlow damit
# von allein wieder aufnahmebereit, statt bis zum Neustart tot zu sein.
HOTKEY_BLOCK_WATCHDOG_SECONDS = 120

# time.time() waere hier nicht nutzbar: audio_callback() bekommt von
# sounddevice selbst einen Parameter namens "time" (ein CFFI-Zeitstempel-
# Objekt, siehe dessen Signatur), der das Modul im Methodenkörper ueberdeckt.
# Diese Referenz auf die Funktion wird VOR der Klasse angelegt, damit sie
# davon unberuehrt bleibt.
_monotonic = time.monotonic


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
        self._hotkey_blocked_since = 0.0

        # "Scharf": erst wenn die Kombination einmal komplett losgelassen
        # wurde, darf sie erneut ausloesen. Verhindert Dauerfeuer, waehrend
        # der Nutzer die Tasten noch haelt.
        self._armed = True

        # Wunsch des Nutzers, unabhaengig davon, ob der Worker-Thread den
        # Audio-Stream schon wirklich geoeffnet hat. Wird ausschliesslich
        # in den Tastatur-Callbacks gesetzt, damit dort keine Zustandsluecke
        # entsteht, waehrend der Worker noch arbeitet.
        self._capture_active = False

        # Befehlswarteschlange fuer den Worker-Thread. Die Tastatur-Callbacks
        # legen hier nur "start"/"stop" hinein und kehren sofort zurueck,
        # siehe ausfuehrliche Begruendung bei _worker_loop().
        self._commands: "queue.Queue[str]" = queue.Queue()
        self._worker_stop = threading.Event()
        self._worker = threading.Thread(
            target=self._worker_loop, name="NovaFlowHotkeyWorker", daemon=True
        )
        self._worker.start()

        # Parse hotkey von Config (unterstützt Combos wie ctrl_win / ctrl_cmd)
        self.hotkey_keys = self._parse_hotkey()

        # Undo per Hotkey (JJ, 2026-07-28): eigene, komplett unabhaengige
        # Tastenkombination, die NICHT die Aufnahme steuert, sondern beim
        # vollstaendigen Druecken sofort Strg+Z/Cmd+Z ans aktive Fenster
        # schickt (siehe _send_undo()). Leer konfiguriert = Funktion aus.
        undo_hotkey_str = config.get("UNDO_HOTKEY", "ctrl_alt_z").strip()
        self.undo_hotkey_keys = (
            self._parse_combo(undo_hotkey_str) if undo_hotkey_str else frozenset()
        )
        # Eigener "scharf"-Zustand, analog zu self._armed, aber unabhaengig
        # von der Aufnahme-Kombination, damit sich beide Hotkeys nicht
        # gegenseitig beeinflussen.
        self._undo_armed = True

        # Stille-Erkennung / Auto-Stop (JJ, 2026-07-28): siehe
        # _evaluate_silence(). Laeuft komplett im Audio-Callback-Thread von
        # sounddevice, nutzt denselben Stop-Weg wie ein manuelles Loslassen
        # der Aufnahmetaste (_handle_stop ueber die Kommando-Warteschlange).
        self._silence_autostop_enabled = config.get_bool("SILENCE_AUTOSTOP_ENABLED", True)
        try:
            self._silence_timeout_seconds = float(config.get("SILENCE_TIMEOUT_SECONDS", 2.5))
        except (TypeError, ValueError):
            self._silence_timeout_seconds = 2.5
        # RMS-Schwelle (normalisierte float32-Samples, Bereich -1.0..1.0):
        # unterhalb gilt ein Audio-Block als "Stille". Kein Config-Feld,
        # bewusst als Konstante: eine zusaetzliche Zahl, die JJ ohne
        # Rueckmeldung vom Mikrofon nicht sinnvoll einstellen koennte.
        self._silence_rms_threshold = 0.015
        self._silence_last_loud_time = 0.0
        self._silence_has_speech = False
        self._silence_autostop_triggered = False

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

    # Modifier-Namen, die als EIN Token erkannt werden (kein Zerlegen in
    # Einzelbuchstaben). Alles andere, was nach dem Zerlegen an "_"/"+"
    # uebrig bleibt und genau ein Zeichen lang ist, gilt als normale Taste
    # (z.B. "z" fuer den Undo-Hotkey) und wird ueber KeyCode.from_char
    # abgebildet, siehe _parse_combo().
    _MODIFIER_KEY_MAP = {
        "alt_gr": keyboard.Key.alt_gr,
        "ctrl": keyboard.Key.ctrl,
        "alt": keyboard.Key.alt,
        "shift": keyboard.Key.shift,
        "win": keyboard.Key.cmd,
        "cmd": keyboard.Key.cmd,
        # Funktionstasten (JJ, 2026-07-28: "f6" als Undo-Hotkey-Option).
        # Ohne diese Zuordnung wuerden "f6" & Co. als unbekanntes Token
        # durchfallen - das betraf bisher schon unbemerkt die bestehenden
        # Hotkey-Optionen "f8"/"f9"/"f10" auf der Diktat-Seite, die dadurch
        # nie wirklich funktioniert haben (stiller Rueckfall auf Alt Gr).
        **{f"f{i}": getattr(keyboard.Key, f"f{i}") for i in range(1, 21) if hasattr(keyboard.Key, f"f{i}")},
    }

    def _parse_hotkey(self) -> frozenset:
        """Parst den Aufnahme-Hotkey aus der Config (unterstützt Combos wie ctrl_win / ctrl_cmd)"""
        return self._parse_combo(self._active_hotkey_str()) or frozenset({keyboard.Key.alt_gr})

    def _parse_combo(self, combo_str: str) -> frozenset:
        """Parst einen beliebigen Tastenkombination-String zu einem frozenset
        von pynput Keys/KeyCodes. Unterstuetzt sowohl reine Modifier-Combos
        (z.B. "ctrl_win") als auch Combos mit einer normalen Taste am Ende
        (z.B. "ctrl_alt_z" fuer den Undo-Hotkey)."""
        combo_str = (combo_str or "").strip().lower()
        if not combo_str:
            return frozenset()

        key_map = self._MODIFIER_KEY_MAP

        if combo_str in key_map:
            return frozenset({key_map[combo_str]})

        parts = combo_str.replace("+", "_").split("_")
        keys = set()
        i = 0
        while i < len(parts):
            if i + 1 < len(parts):
                two = f"{parts[i]}_{parts[i+1]}"
                if two in key_map:
                    keys.add(key_map[two])
                    i += 2
                    continue
            part = parts[i]
            if part in key_map:
                keys.add(key_map[part])
            elif len(part) == 1:
                # Normale Zeichentaste (Buchstabe/Ziffer), z.B. das "z" in
                # "ctrl_alt_z". pynput liefert solche Tasten im Hook als
                # KeyCode-Objekte, nicht als Key-Enum-Member.
                keys.add(keyboard.KeyCode.from_char(part))
            i += 1

        return frozenset(keys)

    def audio_callback(self, indata, frames, time, status):
        """Callback für Audio-Stream.

        ACHTUNG: der Parameter "time" ueberdeckt hier das gleichnamige
        Modul, siehe _monotonic-Referenz oben im Modul, die genau deshalb
        VOR der Klasse angelegt wurde.
        """
        if status:
            logger.debug(f"Audio Status: {status}", f"Audio Status: {status}")

        if self.is_recording and indata is not None:
            self.audio_data.append(indata.copy())

            try:
                rms = float(np.sqrt(np.mean(np.square(indata, dtype=np.float64))))
            except Exception:
                rms = 0.0

            self.update_overlay_level(rms)

            if self._silence_autostop_enabled:
                self._evaluate_silence(rms)

    def _evaluate_silence(self, rms: float):
        """Stoesst bei laengerer Sprechpause automatisch das Ende der
        Aufnahme an (Auto-Stop, JJ 2026-07-28). Nutzt exakt denselben
        Stop-Weg wie ein manuelles Loslassen der Aufnahmetaste
        (_handle_stop ueber die Kommando-Warteschlange), verhaelt sich fuer
        den Rest der Verarbeitungskette also nicht anders.

        Erst NACH der ersten erkannten Sprache aktiv (self._silence_has_speech),
        damit die Aufnahme nicht schon waehrend der allerersten Stille direkt
        nach dem Druecken der Taste sofort wieder beendet wird.
        """
        now = _monotonic()

        if rms >= self._silence_rms_threshold:
            self._silence_last_loud_time = now
            self._silence_has_speech = True
            return

        if not self._silence_has_speech or self._silence_autostop_triggered:
            return

        if (now - self._silence_last_loud_time) >= self._silence_timeout_seconds:
            self._silence_autostop_triggered = True
            logger.info(
                f"Stille erkannt ({self._silence_timeout_seconds:.1f}s) – "
                "Aufnahme wird automatisch beendet.",
                f"Silence detected ({self._silence_timeout_seconds:.1f}s) – "
                "recording stops automatically.",
            )
            self._capture_active = False
            self._block_hotkey()
            self._commands.put("stop")

    def start_recording(self):
        """Startet Audio-Aufnahme und stummschaltet Lautsprecher"""
        try:
            logger.info(
                "Aufnahme gestartet... (Taste loslassen zum Beenden)",
                "Recording started... (Release key to stop)"
            )

            self.audio_data = []
            self.is_recording = True

            # Stille-Erkennung fuer diese Aufnahme zuruecksetzen (siehe
            # _evaluate_silence()).
            self._silence_last_loud_time = _monotonic()
            self._silence_has_speech = False
            self._silence_autostop_triggered = False

            self._mute_audio()

            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                callback=self.audio_callback,
                blocksize=4096
            )
            self.stream.start()

            self.show_overlay()

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
        """Gibt Hotkey nach Text-Injektion wieder frei.

        Loescht bewusst NICHT mehr self._pressed. Das hat frueher dafuer
        gesorgt, dass NovaFlow die tatsaechlich noch gehaltenen Tasten
        "vergisst": wer Strg durchgehend haelt und nur die Windows-Taste
        loslaesst und neu drueckt, kam danach nie wieder auf eine
        vollstaendige Kombination und der Hotkey wirkte tot. Der Satz wird
        jetzt durchgaengig in on_press/on_release gepflegt und bleibt damit
        immer synchron zur Realitaet.
        """
        self._hotkey_blocked = False
        self._hotkey_blocked_since = 0.0
        # Wenn die Kombination gerade nicht (mehr) vollstaendig gehalten
        # wird, sofort wieder scharfstellen. Haelt der Nutzer noch, passiert
        # das automatisch beim naechsten Loslassen.
        if not self.hotkey_keys.issubset(self._pressed):
            self._armed = True
        logger.debug("Hotkey freigegeben", "Hotkey unblocked")
        try:
            from utils.audio_feedback import audio_feedback
            audio_feedback.play_ready()
        except Exception:
            pass

    def _block_hotkey(self):
        """Sperrt den Hotkey und merkt sich den Zeitpunkt (fuer den Watchdog)."""
        self._hotkey_blocked = True
        self._hotkey_blocked_since = time.time()

    def hide_overlay(self):
        """Kompatibilitäts-Stub – überschreibbar durch Subklassen"""
        pass

    def show_overlay(self):
        """Kompatibilitäts-Stub – überschreibbar durch Subklassen.

        Wird beim Start einer Aufnahme aufgerufen (siehe start_recording()),
        die Flowbar-Anzeige (novaflow.pyw) blendet sich hierueber ein.
        """
        pass

    def update_overlay_level(self, rms: float):
        """Kompatibilitäts-Stub – überschreibbar durch Subklassen.

        Wird pro Audio-Block mit dem aktuellen Pegel (RMS, ungefaehr
        0.0-1.0 bei normaler Sprechlautstaerke) aufgerufen, siehe
        audio_callback(). Bewusst getrennt von hide_overlay/show_overlay,
        damit eine Subklasse ohne echte Anzeige (z.B. in Tests) nichts
        weiter tun muss.
        """
        pass

    def _send_undo(self):
        """Schickt Strg+Z (bzw. Cmd+Z unter Mac) ans aktuell aktive Fenster.

        Nutzt bewusst die programmeigene Undo-Funktion des Zielprogramms
        selbst, statt zu versuchen, gezielt nur den zuletzt von NovaFlow
        eingefuegten Text wieder zu entfernen (waere programmuebergreifend
        nicht zuverlaessig umsetzbar). Laeuft im Worker-Thread, nicht im
        Tastatur-Hook, siehe _worker_loop().
        """
        try:
            from pynput.keyboard import Controller

            controller = Controller()
            modifier = self.platform.paste_key()
            controller.press(modifier)
            controller.press('z')
            controller.release('z')
            controller.release(modifier)
            logger.info("Undo gesendet (Strg+Z/Cmd+Z ans aktive Fenster)", "Undo sent (Ctrl+Z/Cmd+Z to active window)")
        except Exception as e:
            logger.error(f"Fehler beim Senden von Undo: {e}", f"Error sending undo: {e}")

    # ------------------------------------------------------------------
    # Tastatur-Callbacks
    #
    # WICHTIG: diese beiden Methoden laufen unter Windows direkt im
    # Low-Level-Keyboard-Hook. Windows raeumt einen Hook kommentarlos ab,
    # wenn dessen Callback laenger als LowLevelHooksTimeout (standardmaessig
    # 300 Millisekunden) braucht. pynput bekommt davon nichts mit,
    # listener.join() kehrt nie zurueck, und damit greift auch die
    # Neustart-Schleife in run() nicht: NovaFlow laeuft dann scheinbar
    # weiter, reagiert aber bis zum Neustart auf keine Taste mehr.
    #
    # Frueher lief hier die komplette Schwerarbeit: pycaw-COM-Aufrufe fuers
    # Stummschalten, Oeffnen und Schliessen des Audiogeraets und das
    # Schreiben der WAV-Datei. Das reisst die 300 Millisekunden regelmaessig.
    # Deshalb tun diese Callbacks jetzt nur noch das Allernoetigste
    # (Zustand merken, Befehl in die Warteschlange legen) und kehren sofort
    # zurueck. Die eigentliche Arbeit macht _worker_loop() in einem eigenen
    # Thread.
    # ------------------------------------------------------------------
    def on_press(self, key):
        """Callback für Tasten-Druck – muss extrem schnell zurückkehren."""
        try:
            norm = self._normalize_key(key)
            # Der Satz wird IMMER gepflegt, auch waehrend der Sperre, damit
            # er nie aus dem Tritt geraet.
            self._pressed.add(norm)

            # Undo-Hotkey: komplett unabhaengig von der Aufnahme-Kombination.
            # Bewusst NUR ausserhalb einer laufenden Aufnahme/Verarbeitung
            # ausgeloest, damit sich das gesendete Strg+Z/Cmd+Z niemals mit
            # der Zwischenablage-Choreografie in flow.inject_text ueberschneidet.
            if (
                self.undo_hotkey_keys
                and self._undo_armed
                and not self.is_recording
                and not self._hotkey_blocked
                and self.undo_hotkey_keys.issubset(self._pressed)
            ):
                self._undo_armed = False
                self._commands.put("undo")

            if self._hotkey_blocked or not self._armed or self._capture_active:
                return
            if self.hotkey_keys.issubset(self._pressed):
                self._capture_active = True
                self._armed = False
                self._commands.put("start")
        except Exception as e:
            # Bewusst nur debug: hier darf niemals eine Ausnahme nach oben
            # durchschlagen, sonst beendet pynput den Listener. Aber im
            # Gegensatz zu frueher wird der Fehler wenigstens protokolliert.
            logger.debug(f"on_press Fehler: {e}", f"on_press error: {e}")

    def on_release(self, key):
        """Callback für Tasten-Release – muss extrem schnell zurückkehren."""
        try:
            norm = self._normalize_key(key)
            self._pressed.discard(norm)

            if self._capture_active and norm in self.hotkey_keys:
                self._capture_active = False
                self._block_hotkey()
                self._commands.put("stop")

            # Kombination nicht mehr vollstaendig gehalten -> wieder scharf.
            if not self.hotkey_keys.issubset(self._pressed) and not self._hotkey_blocked:
                self._armed = True

            if self.undo_hotkey_keys and not self.undo_hotkey_keys.issubset(self._pressed):
                self._undo_armed = True
        except Exception as e:
            logger.debug(f"on_release Fehler: {e}", f"on_release error: {e}")

    # ------------------------------------------------------------------
    # Worker-Thread: erledigt die eigentliche Arbeit ausserhalb des Hooks
    # ------------------------------------------------------------------
    def _worker_loop(self):
        """Arbeitet Start/Stop-Befehle ab, getrennt vom Tastatur-Hook."""
        while not self._worker_stop.is_set():
            try:
                command = self._commands.get(timeout=0.5)
            except queue.Empty:
                self._check_block_watchdog()
                continue

            try:
                if command == "start":
                    self.start_recording()
                elif command == "stop":
                    self._handle_stop()
                elif command == "undo":
                    self._send_undo()
            except Exception as e:
                logger.error(
                    f"Fehler im Hotkey-Worker: {e}", f"Hotkey worker error: {e}"
                )
                # Egal was passiert: die Sperre darf nicht haengen bleiben.
                self.unblock_hotkey()

    def _handle_stop(self):
        """Beendet die Aufnahme und uebergibt sie an die Verarbeitung.

        Der gesamte Ablauf ist so gebaut, dass die Hotkey-Sperre in JEDEM
        Fall wieder faellt. Genau das war vorher der Hauptfehler: die Sperre
        wurde gesetzt, aber nur der Erfolgspfad gab sie wieder frei. Kam aus
        stop_recording() ein None zurueck (zu kurz gedrueckt, also noch kein
        einziger Audioblock angekommen, oder ein Fehler beim Speichern), rief
        niemand mehr unblock_hotkey() auf und NovaFlow war bis zum Neustart
        tot. Auf dem Erfolgspfad gibt weiterhin die Verarbeitungskette frei
        (flow.inject_text, finally-Block), nur dort darf hier nicht doppelt
        freigegeben werden.
        """
        audio_file = None
        try:
            audio_file = self.stop_recording()
        except Exception as e:
            logger.error(
                f"Fehler beim Beenden der Aufnahme: {e}",
                f"Error stopping recording: {e}",
            )

        if not audio_file or not self.hotkey_callback:
            self.unblock_hotkey()
            return

        try:
            self.hotkey_callback(audio_file)
        except Exception as e:
            logger.error(
                f"Fehler in der Verarbeitungskette: {e}",
                f"Error in processing chain: {e}",
            )
            self.unblock_hotkey()

    def _check_block_watchdog(self):
        """Loest eine haengen gebliebene Hotkey-Sperre nach einer Weile."""
        if not self._hotkey_blocked or not self._hotkey_blocked_since:
            return
        if time.time() - self._hotkey_blocked_since < HOTKEY_BLOCK_WATCHDOG_SECONDS:
            return
        logger.warning(
            f"Hotkey war laenger als {HOTKEY_BLOCK_WATCHDOG_SECONDS}s gesperrt "
            "und wird zwangsweise freigegeben.",
            f"Hotkey was blocked for more than {HOTKEY_BLOCK_WATCHDOG_SECONDS}s "
            "and is being force released.",
        )
        self.is_recording = False
        self._capture_active = False
        self.unblock_hotkey()

    def _reset_hotkey_state(self):
        """Setzt den kompletten Tastenzustand auf einen sauberen Ausgangswert."""
        self.is_recording = False
        self._capture_active = False
        self._hotkey_blocked = False
        self._hotkey_blocked_since = 0.0
        self._armed = True
        self._pressed.clear()

    def restart_listener(self):
        """Startet den Tastatur-Listener neu (Notfallknopf aus dem Tray).

        Nutzt der Hotkey ausnahmsweise doch einmal nicht mehr, kann der
        Nutzer damit einen Neustart der gesamten Anwendung vermeiden. Der
        Aufruf beendet den aktuellen Listener, die Schleife in run() legt
        danach von selbst einen neuen an.
        """
        logger.info(
            "Tastatur-Listener wird auf Wunsch neu gestartet...",
            "Restarting keyboard listener on request...",
        )
        self._reset_hotkey_state()
        if self.listener:
            try:
                self.listener.stop()
            except Exception as e:
                logger.debug(f"Listener-Stop Fehler: {e}", f"Listener stop error: {e}")

    def run(self):
        """Startet den Hotkey-Listener (blocking) mit Auto-Restart bei Absturz"""
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
                self._reset_hotkey_state()
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
                self._reset_hotkey_state()
                time.sleep(2)

    def stop(self):
        """Stoppt den Listener, den Worker-Thread und den Restart-Loop"""
        self._running = False
        self._worker_stop.set()
        if self.listener:
            try:
                self.listener.stop()
            except Exception:
                pass

    def cleanup(self):
        """Bereinigung"""
        self._worker_stop.set()

        # Sicherheitsnetz: falls NovaFlow mitten in einer Aufnahme beendet
        # wird, waere die Lautstaerke sonst dauerhaft auf 0 (siehe
        # platforms/windows.py, dort wird gemerkt und auf 0 gesetzt statt
        # echt stummzuschalten).
        try:
            self.platform.audio_mute.unmute()
        except Exception:
            pass

        if self.stream:
            try:
                self.stream.close()
            except Exception:
                pass

        if self.temp_filepath.exists():
            try:
                os.remove(str(self.temp_filepath))
                logger.debug("Temp-Datei gelöscht", "Temp file deleted")
            except Exception as e:
                logger.debug(f"Fehler beim Löschen: {str(e)}", f"Error deleting: {str(e)}")

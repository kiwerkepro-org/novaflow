"""
NovaFlow Main Application
Orchestriert Audio-Aufnahme, Transkription und Text-Injektion.
Unveraendert gegenueber dem bisherigen NovaFlow – die Orchestrierung selbst
war schon plattformunabhaengig, nur core/interface/flow darunter wissen
jetzt ueber platforms/ Bescheid.
"""
import threading
import time
import sys

from core import WhisperCore, VoxtralCore
from interface import FlowInterface
from flow import NovaFlowProcessor
from utils.logger import logger
from utils.config import config, NovaFlowConfig
from utils.history_store import history_store


class NovaFlowApp(FlowInterface):
    """Hauptanwendung - kombiniert alle Module"""

    def __init__(self):
        try:
            NovaFlowConfig.init_env_file()
            language = config.get("LANGUAGE", "de")
            logger.language = language
            logger.info("Initialisiere NovaFlow...", "Initializing NovaFlow...")
            super().__init__(hotkey_callback=self.on_audio_ready)

            # Schutz gegen Doppelverarbeitung
            self._processing_lock = threading.Lock()
            self._last_trigger_time = 0.0

            stt_provider = config.get("STT_PROVIDER", "voxtral").lower()
            if stt_provider == "voxtral":
                logger.info("Initialisiere Voxtral STT (OpenRouter)...", "Initializing Voxtral STT (OpenRouter)...")
                voxtral = VoxtralCore()
                if voxtral.is_available():
                    self.core = voxtral
                    logger.success("Voxtral STT bereit", "Voxtral STT ready")
                else:
                    logger.warning(
                        "Voxtral nicht verfügbar - Fallback auf Whisper",
                        "Voxtral unavailable - falling back to Whisper"
                    )
                    self.core = WhisperCore()
            else:
                logger.info("Lade Whisper-Modell...", "Loading Whisper model...")
                self.core = WhisperCore()

            logger.info("Initialisiere LLM-Provider...", "Initializing LLM provider...")
            self.processor = NovaFlowProcessor()
            logger.success("NovaFlow ist vollständig geladen und bereit!", "NovaFlow is fully loaded and ready!")

        except Exception as e:
            logger.error(f"Fehler bei Initialisierung: {str(e)}", f"Initialization error: {str(e)}")
            raise

    def on_audio_ready(self, audio_filepath):
        """Wird aufgerufen wenn Audio aufgezeichnet wurde"""
        if not audio_filepath:
            return

        now = time.time()
        if now - self._last_trigger_time < 0.3:
            logger.warning(
                "Doppel-Trigger erkannt – ignoriere zweiten Aufruf",
                "Double trigger detected – ignoring second call"
            )
            self.unblock_hotkey()
            return
        self._last_trigger_time = now

        if not self._processing_lock.acquire(blocking=False):
            logger.warning(
                "Verarbeitung läuft bereits – ignoriere Aufnahme",
                "Processing already running – ignoring audio"
            )
            self.unblock_hotkey()
            return

        thread = threading.Thread(
            target=self.process_audio,
            args=(str(audio_filepath),),
            daemon=True
        )
        thread.start()

    def process_audio(self, filepath: str):
        """Pipeline: Audio -> Transkription -> Veredelung -> Injektion"""
        try:
            logger.info("Starte Verarbeitung...", "Starting processing...")
            raw_text = self.core.transcribe_audio(filepath)
            if not raw_text or not raw_text.strip():
                logger.warning(
                    "Keine Sprache erkannt. Bitte lauter sprechen.",
                    "No speech detected. Please speak louder."
                )
                self.unblock_hotkey()
                return
            logger.info(f"Rohtext: {raw_text[:100]}", f"Raw text: {raw_text[:100]}")
            refined_text = self.processor.refine_text(raw_text)
            logger.info(f"Ergebnis: {refined_text[:100]}", f"Result: {refined_text[:100]}")
            history_store.add(raw_text, refined_text)
            self.processor.inject_text(refined_text, interface=self)
        except Exception as e:
            logger.error(f"Fehler bei Audio-Verarbeitung: {str(e)}", f"Error processing audio: {str(e)}")
            self.unblock_hotkey()
        finally:
            if self._processing_lock.locked():
                self._processing_lock.release()

    def run(self):
        """Startet die Hauptanwendung"""
        try:
            super().run()
        except KeyboardInterrupt:
            logger.info("NovaFlow beendet", "NovaFlow stopped")
        finally:
            self.cleanup()


def main():
    """Einstiegspunkt fuer den Konsolen-/Engine-Betrieb (ohne Tray-UI)"""
    try:
        app = NovaFlowApp()
        app.run()
    except Exception as e:
        logger.error(f"Fehler: {str(e)}", f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
